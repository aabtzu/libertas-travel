/* Explore Page — Map markers, info window, legend, geocoding (split from explore.js) */

const MARKER_COLORS = {
    'Restaurant': '#ff6b6b',
    'Bar': '#9c27b0',
    'Cafe': '#8d6e63',
    'Hotel': '#1976d2',
    'Museum': '#00897b',
    'Hiking': '#43a047',
    'Shop': '#fb8c00',
    'Church': '#5e35b1',
    'Activity': '#26a69a',
    'Attraction': '#ef5350',
    'Transportation': '#607d8b',
    'Landmark': '#ff7043'
};

/**
 * Create a colored Leaflet marker icon
 */
function createColoredMarkerIcon(color) {
    return L.divIcon({
        className: 'custom-marker',
        html: `<div style="
            width: 24px;
            height: 24px;
            border-radius: 50% 50% 50% 0;
            background: ${color};
            transform: rotate(-45deg);
            border: 2px solid white;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
        "></div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 24],
        popupAnchor: [0, -24]
    });
}

/**
 * Update map with venues
 */
function updateMap(venueList) {
    if (!map) {
        initMap();
        if (!map) return;
    }

    // Clear existing markers
    clearMap();

    // Filter venues with coordinates
    const venuesWithCoords = venueList.filter(v => v.latitude && v.longitude);

    // If no venues have coords, try to center map on the shared city
    if (venuesWithCoords.length === 0) {
        const cities = [...new Set(venueList.map(v => v.city).filter(c => c))];
        if (cities.length > 0) {
            geocodeCity(cities[0]).then(coords => {
                if (coords && map) map.setView([coords.lat, coords.lng], 12);
            });
        }
        return;
    }

    // Create bounds array for fitting
    const boundsArray = [];

    // Add markers
    venuesWithCoords.forEach(venue => {
        const lat = parseFloat(venue.latitude);
        const lng = parseFloat(venue.longitude);

        // Get color for this venue type
        const color = MARKER_COLORS[venue.venue_type] || '#667eea';

        // Create marker with colored icon
        const marker = L.marker([lat, lng], {
            icon: createColoredMarkerIcon(color),
            title: venue.name
        }).addTo(map);

        // Create popup content
        marker.bindPopup(createInfoWindowContent(venue));

        // Store venue reference for focusVenue
        marker.venueData = venue;

        markers.push(marker);
        boundsArray.push([lat, lng]);
    });

    // Fit map to bounds
    if (boundsArray.length === 1) {
        map.setView(boundsArray[0], 14);
    } else if (boundsArray.length > 1) {
        map.fitBounds(boundsArray, { padding: [50, 50] });
    }

    // Show legend with venue types
    showMapLegend(venueList);
}

/**
 * Create info window content for a venue
 */
function createInfoWindowContent(venue) {
    const location = [venue.city, venue.country].filter(x => x).join(', ');
    const michelin = venue.michelin_stars > 0
        ? `<span style="color: #c62828; font-weight: bold;">★ ${venue.michelin_stars} Michelin</span><br>`
        : '';

    return `
        <div style="max-width: 250px; font-family: sans-serif;">
            <h4 style="margin: 0 0 8px 0; color: #1976d2;">${venue.name}</h4>
            <p style="margin: 0 0 4px 0; color: #666; font-size: 0.9em;">${location}</p>
            ${michelin}
            <p style="margin: 4px 0 0 0; font-size: 0.85em; color: #888;">${venue.venue_type || 'Place'}</p>
        </div>
    `;
}

/**
 * Clear all markers from map
 */
function clearMap() {
    markers.forEach(marker => {
        if (map) {
            map.removeLayer(marker);
        }
    });
    markers = [];
    hideMapLegend();
}

// Store legend control reference
let legendControl = null;

/**
 * Show map legend with venue types
 */
function showMapLegend(venueList) {
    // Remove existing legend
    hideMapLegend();

    if (!map) return;

    // Get unique venue types from current results
    const venueTypes = [...new Set(venueList.map(v => v.venue_type).filter(t => t))];

    if (venueTypes.length === 0) return;

    // Create custom Leaflet control for legend (colors from MARKER_COLORS)
    legendControl = L.control({ position: 'bottomleft' });

    legendControl.onAdd = function(map) {
        const div = L.DomUtil.create('div', 'map-legend');
        div.id = 'map-legend';

        const legendItems = venueTypes.map(type => {
            const color = MARKER_COLORS[type] || '#667eea';
            return `
                <div class="map-legend-item">
                    <span class="map-legend-dot" style="background: ${color}"></span>
                    ${type}
                </div>
            `;
        }).join('');

        div.innerHTML = `
            <div class="map-legend-title">Place Types</div>
            <div class="map-legend-items">${legendItems}</div>
        `;

        // Prevent map interactions when clicking on legend
        L.DomEvent.disableClickPropagation(div);
        L.DomEvent.disableScrollPropagation(div);

        return div;
    };

    legendControl.addTo(map);
}

/**
 * Hide map legend
 */
function hideMapLegend() {
    if (legendControl && map) {
        map.removeControl(legendControl);
        legendControl = null;
    }
}

/**
 * Focus on a specific venue
 */
function focusVenue(venue) {
    if (!map || !venue.latitude || !venue.longitude) return;

    const lat = parseFloat(venue.latitude);
    const lng = parseFloat(venue.longitude);
    map.setView([lat, lng], 16);

    // Find and open the marker popup
    const marker = markers.find(m => m.venueData && m.venueData.name === venue.name);
    if (marker) {
        marker.openPopup();
    }
}

/**
 * Open venue in Google Maps
 */
function openInGoogleMaps(venue) {
    if (venue.google_maps_link) {
        window.open(venue.google_maps_link, '_blank');
    } else if (venue.latitude && venue.longitude) {
        const url = `https://www.google.com/maps/search/?api=1&query=${venue.latitude},${venue.longitude}`;
        window.open(url, '_blank');
    } else {
        const query = encodeURIComponent(`${venue.name} ${venue.city || ''} ${venue.country || ''}`);
        window.open(`https://www.google.com/maps/search/?api=1&query=${query}`, '_blank');
    }
}

/**
 * Geocode a city name to get coordinates for map centering.
 */
async function geocodeCity(city) {
    try {
        const res = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(city)}&format=json&limit=1`, {
            headers: {'User-Agent': 'Libertas-Travel/1.0'}
        });
        const data = await res.json();
        if (data.length > 0) {
            return {lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon)};
        }
    } catch {}
    return null;
}

/**
 * Open venue website
 */
function openWebsite(venue) {
    if (venue.website) {
        window.open(venue.website, '_blank');
    } else {
        // Search for venue
        const query = encodeURIComponent(`${venue.name} ${venue.city || ''}`);
        window.open(`https://www.google.com/search?q=${query}`, '_blank');
    }
}

/**
 * Add venue to a trip's ideas list
 */
let _tripsCache = null;
let _pendingBtn = null;

