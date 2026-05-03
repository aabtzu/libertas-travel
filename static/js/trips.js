/**
 * Libertas - My Trips Page JavaScript
 * Handles view switching, list generation, and map functionality
 */

// Map instance and markers
let tripsMap = null;
let mapMarkers = [];
let mapInitialized = false;

// Geocode cache (shared with localStorage)
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

/**
 * Switch between view tabs
 */
function switchTripsView(view) {
    // Update tab buttons
    document.querySelectorAll('.trips-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.view === view);
    });

    // Update view content
    document.querySelectorAll('.trips-view-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${view}-view`).classList.add('active');

    // The archived section sits outside the view tabs but should follow the
    // active view's layout. Flip its inner container between .trips-grid
    // (card layout) and .trips-list (horizontal-row layout) so archived
    // trips render the same way as active trips.
    const archivedInner = document.querySelector('#archived-section > .trips-grid, #archived-section > .trips-list');
    if (archivedInner) {
        archivedInner.classList.remove('trips-grid', 'trips-list');
        archivedInner.classList.add(view === 'list' ? 'trips-list' : 'trips-grid');
    }
    // In map view the archived section is irrelevant — the map already
    // shows all markers including archived ones (per design).
    const archivedSection = document.getElementById('archived-section');
    const archivedToggle = document.getElementById('show-archived-btn');
    if (archivedSection && archivedToggle) {
        if (view === 'map') {
            archivedSection.style.display = 'none';
            archivedToggle.style.display = 'none';
        } else {
            archivedSection.style.display = '';
            archivedToggle.style.display = '';
        }
    }

    // Initialize specific views if needed
    if (view === 'list') {
        initListView();
    } else if (view === 'map') {
        initMapView();
    }
}

/**
 * Initialize list view by converting card data to list items
 */
function initListView() {
    const container = document.getElementById('trips-list-container');
    const cardsContainer = document.getElementById('trips-container');

    if (!container || !cardsContainer) return;

    // Clone the card wrappers and add to list container
    const cards = cardsContainer.querySelectorAll('.trip-card-wrapper');

    if (cards.length === 0) {
        container.innerHTML = '<div class="no-trips"><i class="fas fa-suitcase"></i><h3>No trips yet</h3><p>Create your first trip to get started!</p></div>';
        return;
    }

    // Clear and repopulate with cloned cards
    container.innerHTML = '';
    cards.forEach(card => {
        const clone = card.cloneNode(true);
        container.appendChild(clone);
    });

    // cloneNode copies the DOM but NOT event listeners. Action handlers
    // are wired via document-level event delegation in upload.js, so clones
    // pick them up automatically.
}

/**
 * Initialize map view
 */
function initMapView() {
    if (mapInitialized) return;

    const mapContainer = document.getElementById('trips-map');
    const loading = mapContainer.querySelector('.map-loading');

    // Initialize Leaflet map
    tripsMap = L.map('trips-map').setView([20, 0], 2);

    LibertasMap.addTileLayer(tripsMap);

    // Hide loading indicator
    if (loading) loading.classList.add('hidden');

    mapInitialized = true;

    // Add markers for each trip
    loadTripMarkers();
}

/**
 * Load trip markers onto the map
 */
async function loadTripMarkers() {
    if (!tripsMap) return;

    // Get trip data from cards — include archived trips on the map
    // (per design: archive ≠ private; archived trips remain visible on the map view)
    const cards = document.querySelectorAll(
        '#trips-container .trip-card-wrapper, #archived-section .trip-card-wrapper'
    );
    const trips = [];

    cards.forEach(card => {
        const link = card.querySelector('.trip-card');
        const title = card.querySelector('.trip-card-title')?.textContent || 'Unknown Trip';
        const dates = card.querySelector('.trip-card-meta span')?.textContent || '';
        const href = link?.getAttribute('href') || '#';

        const mapLocation = card.closest('.trip-card-wrapper')?.dataset.mapLocation || '';
        trips.push({ title, dates, href, mapLocation });
    });

    // Geocode trip destinations in parallel
    const geocodePromises = trips.map(async (trip) => {
        // Prefer the map location from itinerary data (e.g. "Jackson, NH")
        const query = trip.mapLocation || extractDestination(trip.title);
        if (!query) return { trip, coords: null };

        const coords = await geocodeLocation(query);
        return { trip, coords };
    });

    const results = await Promise.all(geocodePromises);

    // Add markers
    const bounds = [];
    results.forEach(({ trip, coords }) => {
        if (coords) {
            const marker = createTripMarker(trip, coords);
            mapMarkers.push(marker);
            bounds.push([coords.lat, coords.lng]);
        }
    });

    // Fit map to markers
    if (bounds.length > 0) {
        if (bounds.length === 1) {
            tripsMap.setView(bounds[0], 6);
        } else {
            tripsMap.fitBounds(bounds, { padding: [50, 50] });
        }
    }
}

/**
 * Extract destination from trip title
 */
function extractDestination(title) {
    // Common destination keywords to look for
    const destinations = [
        // India
        'India', 'Delhi', 'Mumbai', 'Rajasthan', 'Jaipur', 'Agra', 'Goa', 'Kerala', 'Jaisalmer',
        // Asia
        'Japan', 'Tokyo', 'Kyoto', 'Thailand', 'Bangkok', 'Vietnam', 'Hanoi', 'Cambodia', 'Singapore',
        'China', 'Beijing', 'Shanghai', 'Korea', 'Seoul', 'Indonesia', 'Bali',
        // Europe
        'France', 'Paris', 'Italy', 'Rome', 'Venice', 'Florence', 'Milan', 'Spain', 'Barcelona', 'Madrid',
        'Germany', 'Berlin', 'Munich', 'UK', 'London', 'Greece', 'Athens', 'Portugal', 'Lisbon',
        'Netherlands', 'Amsterdam', 'Switzerland', 'Zurich', 'Austria', 'Vienna', 'Prague', 'Dolomites',
        // Americas
        'USA', 'New York', 'Los Angeles', 'San Francisco', 'Chicago', 'Miami', 'Las Vegas', 'Hawaii',
        'Alaska', 'Canada', 'Toronto', 'Vancouver', 'Mexico', 'Cancun', 'Brazil', 'Rio',
        // Other
        'Australia', 'Sydney', 'Melbourne', 'New Zealand', 'Dubai', 'Egypt', 'Morocco', 'Africa', 'Safari'
    ];

    const titleLower = title.toLowerCase();
    for (const dest of destinations) {
        if (titleLower.includes(dest.toLowerCase())) {
            return dest;
        }
    }

    // Return full title as fallback (might not geocode well)
    return title;
}

/**
 * Geocode a location string to coordinates
 */
async function geocodeLocation(query) {
    if (!query) return null;

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
            saveGeocodeCache();
            return result;
        }
    } catch (error) {
        console.error('Geocoding error:', error);
    }

    return null;
}

/**
 * Create a map marker for a trip
 */
function createTripMarker(trip, coords) {
    const marker = L.marker([coords.lat, coords.lng]).addTo(tripsMap);

    const popupContent = `
        <div class="trip-map-popup">
            <h4>${escapeHtml(trip.title)}</h4>
            ${trip.dates ? `<p><i class="fas fa-calendar"></i> ${escapeHtml(trip.dates)}</p>` : ''}
            <a href="${trip.href}">View Trip <i class="fas fa-arrow-right"></i></a>
        </div>
    `;

    marker.bindPopup(popupContent);

    return marker;
}

// escapeHtml() — defined in main.js

// Make switchTripsView globally available
window.switchTripsView = switchTripsView;

/**
 * Fetch LLM-picked card icons in the background and swap them into the DOM.
 *
 * The page renders instantly with keyword-based icons (the synchronous
 * server-side default); these get replaced as Haiku responds. After the
 * first call per trip the icon is cached in itinerary_data, so subsequent
 * page loads return instantly with no LLM call.
 */
async function loadCardIcons() {
    const wrappers = document.querySelectorAll('.trip-card-wrapper[data-link]');
    // Dedupe by link — list view clones cards from cards view, so we'd
    // otherwise call the endpoint twice for the same trip.
    const linksSeen = new Set();
    const tasks = [];
    wrappers.forEach(w => {
        const link = w.dataset.link;
        if (!link || linksSeen.has(link)) return;
        linksSeen.add(link);
        tasks.push(fetchAndApply(link));
    });
    await Promise.all(tasks);
}

async function fetchAndApply(link) {
    try {
        const r = await fetch(`/api/trips/${encodeURIComponent(link)}/card-icon`);
        if (!r.ok) return;
        const data = await r.json();
        // json_ok() doesn't wrap with {success:true}; the response is the
        // raw payload. Bail only if there's no icon field.
        if (!data || !data.icon) return;
        // Apply to ALL wrappers with this link (cards view + list view clones)
        document.querySelectorAll(`.trip-card-wrapper[data-link="${CSS.escape(link)}"] .trip-card-image i`).forEach(iconEl => {
            // Remove existing fa-* class
            [...iconEl.classList].forEach(c => {
                if (c.startsWith('fa-') && c !== 'fas' && c !== 'far' && c !== 'fab') {
                    iconEl.classList.remove(c);
                }
            });
            iconEl.classList.add('fa-' + data.icon);
        });
    } catch (e) {
        // Network error — keep the keyword-based icon
        console.log('Card icon fetch failed for', link, e);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Check for URL hash to switch views
    const hash = window.location.hash.slice(1);
    if (hash && ['cards', 'list', 'map'].includes(hash)) {
        switchTripsView(hash);
    }
    loadCardIcons();
});
