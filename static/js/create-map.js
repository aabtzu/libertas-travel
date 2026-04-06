// ==================== Map View ====================

let tripMap = null;
let mapMarkers = [];

// Load geocode cache from localStorage for persistence
let geocodeCache = {};
try {
    const savedCache = localStorage.getItem('libertas_geocode_cache');
    if (savedCache) {
        geocodeCache = JSON.parse(savedCache);
    }
} catch (e) {
    console.warn('Could not load geocode cache from localStorage');
}

function saveGeocodeCache() {
    try {
        // Only keep the last 500 entries to prevent localStorage from getting too large
        const keys = Object.keys(geocodeCache);
        if (keys.length > 500) {
            const toRemove = keys.slice(0, keys.length - 500);
            toRemove.forEach(k => delete geocodeCache[k]);
        }
        localStorage.setItem('libertas_geocode_cache', JSON.stringify(geocodeCache));
    } catch (e) {
        console.warn('Could not save geocode cache to localStorage');
    }
}

// Category colors for map markers
const CATEGORY_COLORS = {
    'flight': '#3b82f6',
    'transport': '#f59e0b',
    'hotel': '#8b5cf6',
    'lodging': '#8b5cf6',
    'meal': '#ef4444',
    'activity': '#22c55e',
    'attraction': '#06b6d4',
    'other': '#6b7280'
};

/**
 * Switch between itinerary and map tabs
 */
function switchTimelineTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.timeline-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });

    // Update tab content
    document.querySelectorAll('.timeline-tab-content').forEach(content => {
        content.classList.toggle('active', content.id === tabName + '-tab');
    });

    // Initialize map when switching to map tab
    if (tabName === 'map') {
        updateMapDaySelector();
        initializeMap();
    }

    // Render grid when switching to grid tab
    if (tabName === 'grid') {
        renderGrid();
    }

    // Render calendar when switching to calendar tab
    if (tabName === 'calendar') {
        renderCalendar();
    }
}

/**
 * Render the grid view (column table like trip detail pages)
 * Columns: Day | Travel | Activity | Night Stay | Notes
 */
function renderGrid() {
    const container = document.getElementById('grid-container');
    if (!container) return;

    container.innerHTML = '';

    if (currentTrip.days.length === 0) {
        container.innerHTML = `
            <div class="grid-empty">
                <i class="fas fa-th-large" style="font-size: 3rem; color: #ddd; margin-bottom: 16px;"></i>
                <p>No days to display. Add dates or days to your trip first.</p>
            </div>
        `;
        return;
    }

    // Track night stay for carry-forward
    let lastNightStay = null;
    const lastDayNum = currentTrip.days[currentTrip.days.length - 1].day_number;

    // Pre-compute which day indices have lodging, so carry-forward knows when to stop
    const lodgingDayNums = new Set(
        currentTrip.days
            .filter(d => (d.items || []).some(i => ['hotel','lodging'].includes((i.category||'').toLowerCase())))
            .map(d => d.day_number)
    );

    // Build table HTML
    let tableHtml = `
        <div class="column-table-wrapper">
            <table class="column-table">
                <thead>
                    <tr>
                        <th>Day</th>
                        <th>Travel</th>
                        <th>Activity</th>
                        <th>Night Stay</th>
                        <th>Notes</th>
                    </tr>
                </thead>
                <tbody>
    `;

    currentTrip.days.forEach((day, index) => {
        // Categorize items
        const travelItems = [];
        const activityItems = [];
        const lodgingItems = [];
        const notesItems = [];
        let hasFlight = false;

        (day.items || []).forEach(item => {
            const cat = (item.category || 'other').toLowerCase();
            if (cat === 'flight') {
                travelItems.push(item);
                hasFlight = true;
            } else if (cat === 'transport') {
                travelItems.push(item);
            } else if (cat === 'hotel' || cat === 'lodging') {
                lodgingItems.push(item);
            } else if (cat === 'activity' || cat === 'attraction' || cat === 'meal') {
                activityItems.push(item);
            } else {
                notesItems.push(item);
            }
        });

        // Determine night stay
        let currentNightStay = null;
        let isCarried = false;
        if (lodgingItems.length > 0) {
            const lastLodging = lodgingItems[lodgingItems.length - 1];
            currentNightStay = lastLodging.title || lastLodging.location || null;
            lastNightStay = lastLodging;  // store full item so we can check end_date
        } else if (lastNightStay) {
            const isLastDay = (day.day_number === lastDayNum);
            let withinStay = false;
            if (lastNightStay.end_date && day.date) {
                // Has explicit checkout — carry while before that date
                withinStay = day.date < lastNightStay.end_date;
            } else {
                // No end_date — carry until the next day that has its own lodging
                const nextLodgingDay = currentTrip.days
                    .find(d => d.day_number > day.day_number && lodgingDayNums.has(d.day_number));
                withinStay = !nextLodgingDay || day.day_number < nextLodgingDay.day_number;
            }
            if (!isLastDay && !hasFlight && withinStay) {
                currentNightStay = lastNightStay.title || lastNightStay.location || null;
                isCarried = true;
            } else {
                lastNightStay = null;  // stop carrying — checkout reached or next lodging found
            }
        }

        // Format date
        const dateStr = day.date ? formatDate(day.date) : '';
        const dayLabel = `Day ${day.day_number}${dateStr ? '<br><small>' + dateStr + '</small>' : ''}`;

        tableHtml += '<tr>';

        // Day column
        tableHtml += `<td style="font-weight:600;white-space:nowrap;">${dayLabel}</td>`;

        // Travel column
        tableHtml += '<td>' + formatColumnItems(travelItems) + '</td>';

        // Activity column
        tableHtml += '<td>' + formatColumnItems(activityItems) + '</td>';

        // Night Stay column
        if (currentNightStay) {
            const carriedClass = isCarried ? ' carried' : '';
            tableHtml += `<td><div class="night-stay${carriedClass}"><i class="fas fa-bed"></i>${escapeHtml(currentNightStay)}</div></td>`;
        } else {
            tableHtml += '<td><span class="column-empty">-</span></td>';
        }

        // Notes column
        tableHtml += '<td>' + formatColumnItems(notesItems, true) + '</td>';

        tableHtml += '</tr>';
    });

    tableHtml += '</tbody></table></div>';
    container.innerHTML = tableHtml;
}

/**
 * Render the calendar view using shared CalendarView module
 */
function renderCalendar() {
    const container = document.getElementById('calendar-container');
    if (!container) return;

    // Use the shared CalendarView module to render
    container.innerHTML = CalendarView.render(currentTrip, { editable: true });

    // Set up click handlers for calendar items
    setupCalendarClickHandlers(container);
}

/**
 * Set up click handlers for calendar items in the edit view
 */
function setupCalendarClickHandlers(container) {
    // Handle calendar item clicks - show edit dialog
    container.addEventListener('click', function(event) {
        // Handle "+N more" click
        const moreElement = event.target.closest('.calendar-item-more');
        if (moreElement && moreElement.hasAttribute('data-hidden-items')) {
            event.stopPropagation();
            showCalendarMorePopup(moreElement);
            return;
        }

        // Handle calendar item click - open edit modal
        const calendarItem = event.target.closest('.calendar-item');
        if (calendarItem) {
            event.stopPropagation();
            const dayIndex = parseInt(calendarItem.dataset.dayIndex);
            const itemIndex = parseInt(calendarItem.dataset.itemIndex);
            if (!isNaN(dayIndex) && !isNaN(itemIndex)) {
                editItem(dayIndex, itemIndex);
            }
        }
    });
}

/**
 * Show popup with hidden calendar items
 */
function showCalendarMorePopup(element) {
    try {
        const hiddenItems = JSON.parse(element.dataset.hiddenItems);
        // Use existing item detail popup logic
        if (typeof showItemDetailPopup === 'function') {
            // Create a temporary container with the items
            let popupHtml = '<div class="more-items-list">';
            hiddenItems.forEach((item, index) => {
                const iconClass = CalendarView.getCategoryIcon(item.category);
                const detailParts = [];
                if (item.time) detailParts.push(item.time);
                if (item.location) detailParts.push(item.location);

                popupHtml += `
                    <div class="more-item" data-index="${index}">
                        <div class="more-item-header">
                            <i class="fas ${iconClass}"></i>
                            <span class="more-item-title">${escapeHtml(item.title)}</span>
                        </div>
                        ${detailParts.length ? `<div class="more-item-detail">${escapeHtml(detailParts.join(' • '))}</div>` : ''}
                    </div>
                `;
            });
            popupHtml += '</div>';

            // Show as a simple popup near the element
            const popup = document.createElement('div');
            popup.className = 'item-detail-popup calendar-more-popup';
            popup.innerHTML = popupHtml;

            const overlay = document.createElement('div');
            overlay.className = 'item-detail-overlay';
            overlay.onclick = () => { overlay.remove(); popup.remove(); };

            document.body.appendChild(overlay);
            document.body.appendChild(popup);

            // Position the popup
            const rect = element.getBoundingClientRect();
            popup.style.left = Math.min(rect.left, window.innerWidth - 340) + 'px';
            popup.style.top = Math.min(rect.bottom + 5, window.innerHeight - popup.offsetHeight - 10) + 'px';
        }
    } catch (e) {
        console.error('Error showing calendar more popup:', e);
    }
}

/**
 * Format items for a column cell (shared formatting with list view)
 */
function formatColumnItems(items, isNotes = false) {
    if (items.length === 0) {
        return '<span class="column-empty">-</span>';
    }

    return items.map(item => renderItemCard(item, { showNotes: isNotes, compact: true })).join('');
}

/**
 * Shared item card renderer - used by both list and grid views
 */
function renderItemCard(item, options = {}) {
    const { showNotes = false, compact = false, dayIndex = null, itemIndex = null, draggable = false } = options;
    const cat = (item.category || 'other').toLowerCase();
    const iconClass = getItemIcon(item);
    let timeStr = '';
    if (item.time) {
        timeStr = formatTime12Hour(item.time);
        if (item.end_time) {
            const isTravel = (cat === 'travel' || cat === 'flight' || cat === 'transport');
            const separator = isTravel ? ' → ' : ' - ';
            timeStr += separator + formatTime12Hour(item.end_time);
        }
    }
    const locationStr = item.location || '';

    if (compact) {
        // Compact mode for grid view
        let html = `<div class="column-item ${cat}">`;
        html += `<div class="column-item-title"><i class="fas ${iconClass} column-item-icon"></i> ${escapeHtml(item.title)}</div>`;
        if (timeStr) {
            html += `<div class="column-item-time"><i class="fas fa-clock"></i> ${timeStr}</div>`;
        }
        if (locationStr && !showNotes) {
            html += `<div class="column-item-location"><i class="fas fa-map-marker-alt"></i> ${escapeHtml(locationStr)}</div>`;
        }
        if (item.notes && showNotes) {
            html += `<div class="column-item-notes">${escapeHtml(item.notes)}</div>`;
        }
        html += '</div>';
        return html;
    }

    // Full mode for list view
    const draggableAttr = draggable ? 'draggable="true"' : '';
    const dataAttrs = dayIndex !== null ? `data-day-index="${dayIndex}" data-item-index="${itemIndex}"` : '';

    return `
        <div class="item-card ${cat}" ${dataAttrs} ${draggableAttr}>
            <div class="item-icon ${cat}">
                <i class="fas ${iconClass}"></i>
            </div>
            <div class="item-content">
                <div class="item-title">${escapeHtml(item.title)}</div>
                <div class="item-meta">
                    ${timeStr ? `<span><i class="fas fa-clock"></i> ${timeStr}</span>` : ''}
                    ${locationStr ? `<span><i class="fas fa-map-marker-alt"></i> ${locationStr}</span>` : ''}
                </div>
            </div>
            ${dayIndex !== null ? `
            <div class="item-actions">
                <button onclick="editItem(${dayIndex}, ${itemIndex})" title="Edit">
                    <i class="fas fa-edit"></i>
                </button>
                <button onclick="deleteItem(${dayIndex}, ${itemIndex})" title="Delete">
                    <i class="fas fa-trash"></i>
                </button>
            </div>` : ''}
        </div>
    `;
}

/**
 * Get day of week from date string
 */
function getDayOfWeek(dateStr) {
    const date = new Date(dateStr + 'T12:00:00');
    return date.toLocaleDateString('en-US', { weekday: 'long' });
}

// formatDate and escapeHtml are defined in create.js

/**
 * Update the day selector dropdown for map view
 */
function updateMapDaySelector() {
    const select = document.getElementById('map-day-select');
    if (!select) return;

    // Store current selection
    const currentValue = select.value;

    // Rebuild options
    select.innerHTML = '<option value="all">All Days</option>';
    currentTrip.days.forEach((day, index) => {
        const dateStr = day.date ? ` (${formatDateShort(day.date)})` : '';
        select.innerHTML += `<option value="${index}">Day ${day.day_number}${dateStr}</option>`;
    });

    // Restore selection if still valid
    if (currentValue && select.querySelector(`option[value="${currentValue}"]`)) {
        select.value = currentValue;
    }
}

/**
 * Format date for day selector
 */
function formatDateShort(dateStr) {
    const date = new Date(dateStr + 'T00:00:00');
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/**
 * Initialize the Leaflet map
 */
async function initializeMap() {
    const mapContainer = document.getElementById('trip-map');
    const mapLoading = document.getElementById('map-loading');

    if (!mapContainer) return;

    // If map already exists, just update markers
    if (tripMap) {
        updateMapForDay();
        return;
    }

    // Try to get initial center from trip destination
    let initialCenter = [20, 0]; // World view fallback
    let initialZoom = 2;

    const tripDestination = extractDestinationFromTrip();
    if (tripDestination) {
        const coords = await geocodeLocation(tripDestination);
        if (coords) {
            initialCenter = [coords.lat, coords.lng];
            initialZoom = 12;
        }
    }

    // Create map
    tripMap = L.map('trip-map').setView(initialCenter, initialZoom);

    // Add tile layer from shared config
    LibertasMap.addTileLayer(tripMap);

    // Hide loading and update markers
    if (mapLoading) mapLoading.classList.add('hidden');
    updateMapForDay();
}

/**
 * Update map markers based on selected day
 */
async function updateMapForDay() {
    if (!tripMap) return;

    const select = document.getElementById('map-day-select');
    const selectedDay = select ? select.value : 'all';

    // Clear existing markers
    mapMarkers.forEach(marker => tripMap.removeLayer(marker));
    mapMarkers = [];

    // Collect items to show
    let itemsToShow = [];

    if (selectedDay === 'all') {
        currentTrip.days.forEach((day, dayIndex) => {
            (day.items || []).forEach(item => {
                itemsToShow.push({ ...item, dayIndex, dayNumber: day.day_number });
            });
        });
    } else {
        const dayIndex = parseInt(selectedDay);
        const day = currentTrip.days[dayIndex];
        if (day && day.items) {
            day.items.forEach(item => {
                itemsToShow.push({ ...item, dayIndex, dayNumber: day.day_number });
            });
        }
    }

    // Get destination context from trip title or items
    const tripDestination = extractDestinationFromTrip();

    // Filter items with locations, excluding origin/return flights
    const itemsWithLocation = itemsToShow.filter(item => {
        if (!item.location && !item.title) return false;

        // Exclude flights that are departures from home/origin
        if (item.category === 'flight') {
            const loc = (item.location || '').toLowerCase();
            const title = (item.title || '').toLowerCase();
            // Skip if it's a departure flight (location is origin airport)
            // Common patterns: "FCO", "Rome (Fiumicino)", airport codes
            if (isOriginAirport(loc, title, tripDestination)) {
                return false;
            }
        }

        return true;
    });

    if (itemsWithLocation.length === 0) {
        showNoLocationsMessage();
        return;
    }

    // Geocode and add markers
    const bounds = [];

    // Build geo queries and geocode in parallel for faster loading
    const geocodePromises = itemsWithLocation.map(async (item) => {
        const searchQuery = buildGeoQuery(item, tripDestination);
        const coords = await geocodeLocation(searchQuery);
        return { item, coords };
    });

    const results = await Promise.all(geocodePromises);

    // Add markers for successful geocodes
    for (const { item, coords } of results) {
        if (coords) {
            const marker = createMapMarker(item, coords);
            mapMarkers.push(marker);
            bounds.push([coords.lat, coords.lng]);
        }
    }

    // Fit map to markers
    if (bounds.length > 0) {
        if (bounds.length === 1) {
            tripMap.setView(bounds[0], 15);
        } else {
            tripMap.fitBounds(bounds, { padding: [50, 50] });
        }
    }
}

/**
 * Extract destination/city from trip context
 */
function extractDestinationFromTrip() {
    const cityPatterns = ['Florence', 'Rome', 'Venice', 'Milan', 'Naples', 'Paris',
        'London', 'Barcelona', 'Madrid', 'Amsterdam', 'Berlin', 'Vienna', 'Prague',
        'Lisbon', 'Dublin', 'Edinburgh', 'Athens', 'Istanbul', 'Tokyo', 'Kyoto',
        'New York', 'Los Angeles', 'San Francisco', 'Chicago', 'Boston', 'Seattle',
        'Bratislava', 'Budapest', 'Munich', 'Salzburg', 'Zurich', 'Geneva'];

    // First, try extracting from trip title (most reliable)
    const title = currentTrip.title || '';
    for (const city of cityPatterns) {
        if (title.toLowerCase().includes(city.toLowerCase())) {
            return city;
        }
    }

    // Count city mentions in non-flight items (skip flights as they include origin)
    const cityCounts = {};
    currentTrip.days.forEach(day => {
        (day.items || []).forEach(item => {
            // Skip flights - they often have origin city
            if (item.category === 'flight') return;

            const loc = (item.location || '').toLowerCase();
            for (const city of cityPatterns) {
                if (loc.includes(city.toLowerCase())) {
                    cityCounts[city] = (cityCounts[city] || 0) + 1;
                }
            }
        });
    });

    // Return most mentioned city
    const sorted = Object.entries(cityCounts).sort((a, b) => b[1] - a[1]);
    if (sorted.length > 0) {
        return sorted[0][0];
    }

    // Return trip title as fallback
    return title;
}

/**
 * Check if a location is an origin/home airport (not part of destination)
 */
function isOriginAirport(location, title, destination) {
    if (!destination) return false;

    const destLower = destination.toLowerCase();

    // Common home/origin cities to exclude
    const homeCities = ['rome', 'fiumicino', 'fco', 'jfk', 'lax', 'sfo', 'ord', 'lhr', 'cdg'];

    // If destination is in the location, it's not an origin airport
    if (location.includes(destLower)) return false;

    // Check if location contains home city patterns
    for (const home of homeCities) {
        if (location.includes(home) && !destLower.includes(home)) {
            return true;
        }
    }

    // Check flight title patterns like "FCO - VIE" - first part is origin
    const flightMatch = title.match(/([a-z]{3})\s*[-–]\s*([a-z]{3})/i);
    if (flightMatch) {
        const origin = flightMatch[1].toLowerCase();
        const dest = flightMatch[2].toLowerCase();
        // If location matches origin airport, exclude it
        if (location.includes(origin)) return true;
    }

    return false;
}

/**
 * Build a geocoding query with destination context
 */
function buildGeoQuery(item, destination) {
    const location = item.location || '';
    const title = item.title || '';

    // If location has a full address (with comma or long), use it directly
    if (location && location.includes(',') && location.length > 20) {
        return location;
    }

    // For items with location, add destination context if not already present
    if (location) {
        const locLower = location.toLowerCase();
        const destLower = (destination || '').toLowerCase();

        // Skip adding context if location already has the destination
        if (destLower && locLower.includes(destLower)) {
            return location;
        }

        // Skip adding context if location looks like a full address
        if (location.match(/\d+.*\d{4,}/)) {  // Has numbers like street address + postal code
            return location;
        }

        // Add destination context
        if (destination) {
            return `${location}, ${destination}`;
        }
        return location;
    }

    // Use title with destination context for items without location
    if (title && destination) {
        // Skip generic titles
        if (title.toLowerCase().includes('stay') || title.toLowerCase().includes('flight')) {
            return destination;
        }
        return `${title}, ${destination}`;
    }

    // Fallback
    return location || title || destination;
}

/**
 * Geocode a location string to coordinates using Nominatim
 */
async function geocodeLocation(query) {
    if (!query) return null;

    // Check cache first
    const cacheKey = query.toLowerCase().trim();
    if (geocodeCache[cacheKey]) {
        return geocodeCache[cacheKey];
    }

    try {
        const response = await fetch(
            `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`,
            {
                headers: {
                    'User-Agent': 'Libertas Travel Planner'
                }
            }
        );

        const data = await response.json();

        if (data && data.length > 0) {
            const result = {
                lat: parseFloat(data[0].lat),
                lng: parseFloat(data[0].lon)
            };
            geocodeCache[cacheKey] = result;
            saveGeocodeCache();  // Persist to localStorage
            return result;
        }
    } catch (error) {
        console.error('Geocoding error:', error);
    }

    return null;
}

/**
 * Create a map marker for an item
 */
function createMapMarker(item, coords) {
    const color = CATEGORY_COLORS[item.category] || CATEGORY_COLORS.other;
    const iconClass = getItemIcon(item);

    // Create custom icon
    const customIcon = L.divIcon({
        className: 'leaflet-custom-marker',
        html: `<div style="width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3);background-color:${color};">
                   <i class="fas ${iconClass}" style="color:white;font-size:14px;"></i>
               </div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
        popupAnchor: [0, -16]
    });

    // Build popup content
    const timeStr = item.time ? `<div><i class="fas fa-clock"></i> ${formatTime12Hour(item.time)}</div>` : '';
    const locationStr = item.location ? `<div><i class="fas fa-map-marker-alt"></i> ${escapeHtml(item.location)}</div>` : '';
    const dayStr = item.dayNumber ? `<div class="marker-day">Day ${item.dayNumber}</div>` : '';

    const popupContent = `
        <div class="marker-popup">
            ${dayStr}
            <div class="marker-title">${escapeHtml(item.title)}</div>
            <div class="marker-meta">
                ${timeStr}
                ${locationStr}
            </div>
        </div>
    `;

    const marker = L.marker([coords.lat, coords.lng], { icon: customIcon })
        .addTo(tripMap)
        .bindPopup(popupContent);

    return marker;
}

/**
 * Show message when no locations are available
 */
function showNoLocationsMessage() {
    const mapContainer = document.getElementById('trip-map');
    if (!mapContainer) return;

    // Check if message already exists
    if (!mapContainer.querySelector('.map-no-locations')) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'map-no-locations';
        messageDiv.innerHTML = `
            <i class="fas fa-map-marked-alt"></i>
            <p>No locations to display.<br>Add items with locations to see them on the map.</p>
        `;
        mapContainer.appendChild(messageDiv);
    }
}

// Make functions available globally
window.switchTimelineTab = switchTimelineTab;
window.updateMapForDay = updateMapForDay;
