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
// First-time hint above the chat. Shown once per browser, then hidden
// forever (libertas_seen_explore_intro in localStorage).
function maybeShowExploreIntro() {
    const intro = document.getElementById('explore-intro');
    if (!intro) return;
    let seen = false;
    try { seen = localStorage.getItem('libertas_seen_explore_intro') === '1'; } catch (e) {}
    if (seen) return;
    intro.removeAttribute('hidden');
    document.getElementById('explore-intro-close')?.addEventListener('click', () => {
        intro.setAttribute('hidden', '');
        try { localStorage.setItem('libertas_seen_explore_intro', '1'); } catch (e) {}
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    maybeShowExploreIntro();
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

    // Use shared chat utilities for history and cancel support
    LibertasChat.init({
        inputId: 'chat-input',
        sendBtnId: 'chat-send-btn',
        onSend: handleChatMessage,
        onCancel: () => {
            hideTypingIndicator();
            addMessage('assistant', 'Request cancelled.');
        }
    });

    // Quick suggestion clicks
    document.querySelectorAll('.suggestion-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            input.value = chip.textContent;
            // Trigger input event to let LibertasChat handle it
            input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
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
 * Handle a chat message (called by LibertasChat)
 */
async function handleChatMessage(message, abortController) {
    const input = document.getElementById('chat-input');

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
            }),
            signal: abortController.signal
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
        if (error.name === 'AbortError') {
            throw error; // Re-throw to let LibertasChat handle it
        }
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

    // Source badge (CURATED vs AI_PICK)
    const source = venue.source || 'CURATED';
    const sourceBadgeClass = source === 'CURATED' ? 'curated' : 'ai-pick';
    const sourceBadgeText = source === 'CURATED' ? 'Curated' : 'AI Pick';
    const sourceBadge = `<span class="source-badge ${sourceBadgeClass}">${sourceBadgeText}</span>`;

    // Collection tag (origin)
    const collectionTag = venue.collection && venue.collection !== 'Saved'
        ? `<span class="collection-tag" title="${venue.collection}">${venue.collection}</span>`
        : '';

    // Michelin badge
    const michelinBadge = venue.michelin_stars > 0
        ? `<div class="michelin-badge"><i class="fas fa-star"></i> ${venue.michelin_stars} Michelin</div>`
        : '';

    // Cuisine tag
    const cuisineTag = venue.cuisine_type
        ? `<span class="venue-card-tag">${venue.cuisine_type}</span>`
        : '';

    const location = buildVenueLocation(venue);

    // Description (truncated to ~100 chars)
    let description = venue.description || venue.notes || '';
    if (description.length > 120) {
        description = description.substring(0, 117) + '...';
    }
    const descriptionHtml = description
        ? `<div class="venue-card-description">${description}</div>`
        : '';

    return `
        <div class="venue-card" data-name="${venue.name}" data-source="${source}">
            <div class="venue-card-image ${venueType}">
                <i class="fas ${icon} placeholder-icon"></i>
                <div class="venue-type-badge">${venue.venue_type || 'Place'}</div>
                ${michelinBadge}
            </div>
            <div class="venue-card-content">
                <div class="venue-card-header">
                    <div class="source-badges">${sourceBadge}${collectionTag}</div>
                </div>
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
                    <button class="venue-action-btn add-to-trip" data-venue='${JSON.stringify({name: venue.name, city: venue.city, state: venue.state, country: venue.country, venue_type: venue.venue_type, cuisine_type: venue.cuisine_type, latitude: venue.latitude, longitude: venue.longitude, website: venue.website, google_maps_link: venue.google_maps_link}).replace(/'/g, "&#39;")}' title="Add this venue to one of your trips">
                        <i class="fas fa-plus"></i> Add to trip
                    </button>
                </div>
            </div>
        </div>
    `;
}

// Marker colors matching the legend
