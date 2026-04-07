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

// CATEGORY_COLORS is defined in main.js

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
