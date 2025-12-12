/**
 * Libertas Explore - Chat-based venue discovery
 */

// Global state
let venues = [];
let filteredVenues = [];
let map = null;
let markers = [];
let chatHistory = [];

// Session storage keys
const STORAGE_KEY_CHAT = 'libertas_explore_chat';
const STORAGE_KEY_VENUES = 'libertas_explore_venues';

/**
 * Save state to sessionStorage
 */
function saveState() {
    try {
        sessionStorage.setItem(STORAGE_KEY_CHAT, JSON.stringify(chatHistory));
        sessionStorage.setItem(STORAGE_KEY_VENUES, JSON.stringify(filteredVenues));
    } catch (e) {
        console.warn('Could not save explore state:', e);
    }
}

/**
 * Load state from sessionStorage
 */
function loadState() {
    try {
        const savedChat = sessionStorage.getItem(STORAGE_KEY_CHAT);
        const savedVenues = sessionStorage.getItem(STORAGE_KEY_VENUES);

        if (savedChat) {
            chatHistory = JSON.parse(savedChat);
        }
        if (savedVenues) {
            filteredVenues = JSON.parse(savedVenues);
        }

        return chatHistory.length > 0;
    } catch (e) {
        console.warn('Could not load explore state:', e);
        return false;
    }
}

/**
 * Restore UI from saved state
 */
function restoreUI() {
    const messagesContainer = document.getElementById('chat-messages');

    // Rebuild chat messages
    chatHistory.forEach(msg => {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${msg.role}`;

        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.innerHTML = msg.role === 'assistant'
            ? '<i class="fas fa-feather-alt"></i>'
            : '<i class="fas fa-user"></i>';

        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        bubble.innerHTML = formatMessageContent(msg.content);

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(bubble);
        messagesContainer.appendChild(messageDiv);
    });

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // Restore venues display
    if (filteredVenues.length > 0) {
        displayVenues(filteredVenues);
        // Map will be updated after it initializes
    }
}

// Venue type icons
const VENUE_ICONS = {
    'Restaurant': 'fa-utensils',
    'Bar': 'fa-martini-glass',
    'Cafe': 'fa-mug-hot',
    'Hotel': 'fa-bed',
    'Museum': 'fa-landmark',
    'Hiking': 'fa-mountain',
    'Shop': 'fa-bag-shopping',
    'Church': 'fa-church',
    'Activity': 'fa-person-hiking',
    'Attraction': 'fa-camera',
    'Transportation': 'fa-train',
    'Landmark': 'fa-monument'
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    await loadVenues();
    initChat();
    initMap();

    // Initialize mobile sidebar (uses shared function from main.js)
    if (typeof initMobileSidebar === 'function') {
        initMobileSidebar({
            sidebarId: 'explore-sidebar',
            fabId: 'explore-chat-fab',
            overlayId: 'explore-sidebar-overlay',
            closeBtnId: 'explore-sidebar-close'
        });
    }

    // Check for saved state
    const hasState = loadState();
    if (hasState) {
        // Restore previous session
        restoreUI();
        // Update map with saved venues after a short delay for map to initialize
        if (filteredVenues.length > 0) {
            setTimeout(() => updateMap(filteredVenues), 500);
        }
    } else {
        // Fresh session - show welcome
        showWelcomeMessage();
    }
});

/**
 * Load venues from the API
 */
async function loadVenues() {
    try {
        const response = await fetch('/api/explore/venues');
        if (response.ok) {
            venues = await response.json();
            console.log(`Loaded ${venues.length} venues`);
        } else {
            console.error('Failed to load venues');
        }
    } catch (error) {
        console.error('Error loading venues:', error);
    }
}

/**
 * Initialize chat functionality
 */
function initChat() {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send-btn');

    // Send on button click
    sendBtn.addEventListener('click', sendMessage);

    // Send on Enter (but not Shift+Enter for multi-line)
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize textarea
    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });

    // Quick suggestion clicks
    document.querySelectorAll('.suggestion-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            input.value = chip.textContent;
            sendMessage();
        });
    });
}

/**
 * Initialize Leaflet Map
 */
function initMap() {
    const mapContainer = document.getElementById('explore-map');
    if (!mapContainer || typeof L === 'undefined') {
        console.log('Map not initialized - waiting for Leaflet');
        return;
    }

    // Remove placeholder if present
    const placeholder = mapContainer.querySelector('.map-placeholder');
    if (placeholder) {
        placeholder.style.display = 'none';
    }

    map = L.map(mapContainer, {
        center: [40.7128, -74.0060], // NYC default
        zoom: 3,
        zoomControl: true
    });

    // Add tile layer from shared config
    LibertasMap.addTileLayer(map);
}

/**
 * Show welcome message
 */
function showWelcomeMessage() {
    const welcomeText = `Hello! I'm your travel assistant. I have access to over 2,000 curated places worldwide - restaurants, bars, cafes, hotels, museums, hiking spots, and more.

What would you like to explore? You can ask me things like:
- "Show me Japanese restaurants in Tokyo"
- "Find bars in Rome"
- "What Michelin-starred places do you have?"
- "Hiking spots in Iceland"`;

    addMessage('assistant', welcomeText);
}

/**
 * Send a chat message
 */
async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();

    if (!message) return;

    // Add user message to chat
    addMessage('user', message);
    input.value = '';
    input.style.height = 'auto';

    // Show typing indicator
    showTypingIndicator();

    // Send to API
    try {
        const response = await fetch('/api/explore/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                history: chatHistory.slice(-10) // Send last 10 messages for context
            })
        });

        hideTypingIndicator();

        if (response.ok) {
            const data = await response.json();

            // Add assistant response
            addMessage('assistant', data.response);

            // Update venues if search results returned
            if (data.venues && data.venues.length > 0) {
                filteredVenues = data.venues;
                displayVenues(filteredVenues);
                updateMap(filteredVenues);
                saveState();
            } else if (data.clear_results) {
                filteredVenues = [];
                displayVenues([]);
                clearMap();
                saveState();
            }
        } else {
            addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
        }
    } catch (error) {
        hideTypingIndicator();
        console.error('Chat error:', error);
        addMessage('assistant', 'Sorry, I couldn\'t connect to the server. Please try again.');
    }
}

/**
 * Add a message to the chat
 */
function addMessage(role, content) {
    const messagesContainer = document.getElementById('chat-messages');

    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.innerHTML = role === 'assistant'
        ? '<i class="fas fa-feather-alt"></i>'
        : '<i class="fas fa-user"></i>';

    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.innerHTML = formatMessageContent(content);

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(bubble);
    messagesContainer.appendChild(messageDiv);

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // Add to history
    chatHistory.push({ role, content });

    // Save state
    saveState();
}

/**
 * Format message content with basic markdown-like styling
 */
function formatMessageContent(content) {
    // Convert newlines to <br>
    let formatted = content.replace(/\n/g, '<br>');

    // Bold text **text**
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Italic text *text*
    formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');

    return formatted;
}

/**
 * Show typing indicator
 */
function showTypingIndicator() {
    const messagesContainer = document.getElementById('chat-messages');

    const indicator = document.createElement('div');
    indicator.id = 'typing-indicator';
    indicator.className = 'chat-message assistant';
    indicator.innerHTML = `
        <div class="avatar"><i class="fas fa-feather-alt"></i></div>
        <div class="bubble typing-indicator">
            <span></span><span></span><span></span>
        </div>
    `;

    messagesContainer.appendChild(indicator);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Hide typing indicator
 */
function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

/**
 * Display venues in the results area
 */
function displayVenues(venueList) {
    const resultsContainer = document.getElementById('venue-results');
    const countElement = document.getElementById('results-count');

    // Update count
    countElement.textContent = `${venueList.length} places`;

    if (venueList.length === 0) {
        resultsContainer.innerHTML = `
            <div class="empty-results">
                <i class="fas fa-compass"></i>
                <h4>No places to show yet</h4>
                <p>Ask me about destinations you'd like to explore!</p>
            </div>
        `;
        return;
    }

    // Generate venue cards
    resultsContainer.innerHTML = venueList.map(venue => createVenueCard(venue)).join('');

    // Add click handlers
    resultsContainer.querySelectorAll('.venue-card').forEach((card, index) => {
        card.addEventListener('click', () => focusVenue(venueList[index]));
    });

    resultsContainer.querySelectorAll('.venue-action-btn.maps').forEach((btn, index) => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            openInGoogleMaps(venueList[index]);
        });
    });

    resultsContainer.querySelectorAll('.venue-action-btn.website').forEach((btn, index) => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            openWebsite(venueList[index]);
        });
    });
}

/**
 * Create HTML for a venue card
 */
function createVenueCard(venue) {
    const venueType = (venue.venue_type || 'other').toLowerCase();
    const icon = VENUE_ICONS[venue.venue_type] || 'fa-map-marker-alt';

    // Michelin badge
    const michelinBadge = venue.michelin_stars > 0
        ? `<div class="michelin-badge"><i class="fas fa-star"></i> ${venue.michelin_stars} Michelin</div>`
        : '';

    // Cuisine tag
    const cuisineTag = venue.cuisine_type
        ? `<span class="venue-card-tag">${venue.cuisine_type}</span>`
        : '';

    // Location string
    const location = [venue.city, venue.state, venue.country]
        .filter(x => x)
        .join(', ');

    // Description (truncated to ~100 chars)
    let description = venue.description || venue.notes || '';
    if (description.length > 120) {
        description = description.substring(0, 117) + '...';
    }
    const descriptionHtml = description
        ? `<div class="venue-card-description">${description}</div>`
        : '';

    return `
        <div class="venue-card" data-name="${venue.name}">
            <div class="venue-card-image ${venueType}">
                <i class="fas ${icon} placeholder-icon"></i>
                <div class="venue-type-badge">${venue.venue_type || 'Place'}</div>
                ${michelinBadge}
            </div>
            <div class="venue-card-content">
                <div class="venue-card-name" title="${venue.name}">${venue.name}</div>
                <div class="venue-card-location">
                    <i class="fas fa-map-marker-alt"></i>
                    ${location}
                </div>
                ${descriptionHtml}
                <div class="venue-card-meta">
                    ${cuisineTag}
                </div>
                <div class="venue-card-actions">
                    <button class="venue-action-btn maps">
                        <i class="fas fa-map"></i> Map
                    </button>
                    <button class="venue-action-btn website">
                        <i class="fas fa-globe"></i> Website
                    </button>
                </div>
            </div>
        </div>
    `;
}

// Marker colors matching the legend
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

    if (venuesWithCoords.length === 0) return;

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

    // Legend color mapping
    const legendColors = {
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

    // Create custom Leaflet control for legend
    legendControl = L.control({ position: 'bottomleft' });

    legendControl.onAdd = function(map) {
        const div = L.DomUtil.create('div', 'map-legend');
        div.id = 'map-legend';

        const legendItems = venueTypes.map(type => {
            const color = legendColors[type] || '#667eea';
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

// Export initMap for manual initialization if needed
window.initMap = initMap;
