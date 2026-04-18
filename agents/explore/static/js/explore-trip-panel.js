/**
 * Pinned trip panel for Explore.
 * When a trip is pinned, shows current ideas and marks already-added venues.
 * Depends on globals from explore.js: sendToTrip, showTripPicker, _tripsCache
 * Depends on globals from main.js: escapeHtml, CATEGORY_ICONS
 */

let _pinnedTrip = null;    // {link, title}
let _pinnedItems = [];     // items already in the trip

/**
 * Pin a trip as the active building target and load its ideas.
 */
async function pinTrip(link, title) {
    _pinnedTrip = {link, title};

    try {
        const res = await fetch(`/api/trips/${link}/data`);
        if (res.ok) {
            const data = await res.json();
            const idata = data.trip?.itinerary_data || {};
            _pinnedItems = idata.ideas || [];
        }
    } catch {
        _pinnedItems = [];
    }

    // Hide toggle if visible, show panel
    document.getElementById('trip-panel-toggle').style.display = 'none';
    renderTripPanel();
    markAddedVenues();
}

/**
 * Minimize the panel (keep trip pinned, hide panel, show toggle button).
 */
function minimizeTripPanel() {
    document.getElementById('trip-panel').style.display = 'none';
    const toggle = document.getElementById('trip-panel-toggle');
    toggle.style.display = 'flex';
    const countEl = document.getElementById('trip-panel-toggle-count');
    if (countEl) countEl.textContent = _pinnedItems.length || '';
}

/**
 * Re-open the minimized panel.
 */
function showTripPanel() {
    if (!_pinnedTrip) return;
    renderTripPanel();
    document.getElementById('trip-panel-toggle').style.display = 'none';
}

/**
 * Fully unpin the current trip.
 */
function unpinTrip() {
    _pinnedTrip = null;
    _pinnedItems = [];
    document.getElementById('trip-panel').style.display = 'none';
    document.getElementById('trip-panel-toggle').style.display = 'none';
    document.querySelectorAll('.venue-action-btn.added').forEach(btn => {
        btn.innerHTML = '<i class="fas fa-plus"></i> Trip';
        btn.disabled = false;
        btn.classList.remove('added');
    });
}

/**
 * Check if a venue name is already in the pinned trip.
 */
function isAlreadyInTrip(name) {
    if (!_pinnedTrip || !name) return false;
    const lower = name.toLowerCase();
    return _pinnedItems.some(i => i.title.toLowerCase() === lower);
}

/**
 * Render the trip panel with current items grouped by category.
 */
function renderTripPanel() {
    const panel = document.getElementById('trip-panel');
    const nameEl = document.getElementById('trip-panel-name');
    const itemsEl = document.getElementById('trip-panel-items');

    panel.style.display = 'flex';
    nameEl.textContent = _pinnedTrip.title;

    if (_pinnedItems.length === 0) {
        itemsEl.innerHTML = '<div class="trip-panel-empty">No items yet — add from venue cards</div>';
        return;
    }

    // Group by category
    const groups = {};
    for (const item of _pinnedItems) {
        const cat = item.category || 'other';
        if (!groups[cat]) groups[cat] = [];
        groups[cat].push(item);
    }

    const labels = {
        meal: 'Restaurants', activity: 'Activities', attraction: 'Attractions',
        hotel: 'Hotels', other: 'Other'
    };

    let html = '';
    for (const [cat, items] of Object.entries(groups)) {
        const label = labels[cat] || cat;
        const icon = CATEGORY_ICONS[cat] || 'fa-map-marker-alt';
        html += `<div class="trip-panel-group">`;
        html += `<div class="trip-panel-group-header"><i class="fas ${icon}"></i> ${label} (${items.length})</div>`;
        for (const item of items) {
            html += `<div class="trip-panel-item">
                <span class="trip-panel-item-name">${escapeHtml(item.title)}</span>
                ${item.location ? `<span class="trip-panel-item-loc">${escapeHtml(item.location)}</span>` : ''}
            </div>`;
        }
        html += `</div>`;
    }

    itemsEl.innerHTML = html;

    // Also update toggle count if it's visible
    const countEl = document.getElementById('trip-panel-toggle-count');
    if (countEl) countEl.textContent = _pinnedItems.length || '';
}

/**
 * Mark venue cards whose names match items already in the pinned trip.
 */
function markAddedVenues() {
    if (!_pinnedTrip) return;
    document.querySelectorAll('.venue-action-btn.add-to-trip').forEach(btn => {
        try {
            const venue = JSON.parse(btn.dataset.venue);
            if (isAlreadyInTrip(venue.name)) {
                btn.innerHTML = '<i class="fas fa-check"></i> Added';
                btn.disabled = true;
                btn.classList.add('added');
            }
        } catch {}
    });
}

// --- Event listeners ---

document.getElementById('trip-panel-close')?.addEventListener('click', minimizeTripPanel);
document.getElementById('trip-panel-toggle')?.addEventListener('click', showTripPanel);

// Switch button: show trip picker to change target
document.getElementById('trip-panel-switch')?.addEventListener('click', async () => {
    unpinTrip();
    // Fetch fresh trips list
    try {
        const res = await fetch('/api/trips/list');
        if (res.ok) {
            const data = await res.json();
            _tripsCache = data.trips || [];
        }
    } catch { return; }

    showTripPicker(_tripsCache || [], async (link) => {
        const trip = (_tripsCache || []).find(t => t.link === link);
        if (trip) pinTrip(link, trip.title);
    });
});

// Re-mark venues after new search results are displayed
const _origDisplayVenues = typeof displayVenues === 'function' ? displayVenues : null;
if (_origDisplayVenues) {
    const _real = displayVenues;
    window.displayVenues = function(venues) {
        _real(venues);
        if (_pinnedTrip) markAddedVenues();
    };
}
