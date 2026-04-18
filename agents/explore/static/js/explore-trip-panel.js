/**
 * Pinned trip panel for Explore.
 * When a trip is pinned, shows current ideas and marks already-added venues.
 * Depends on globals from explore.js: sendToTrip, displayVenues
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

    renderTripPanel();
    markAddedVenues();
}

/**
 * Unpin the current trip.
 */
function unpinTrip() {
    _pinnedTrip = null;
    _pinnedItems = [];
    document.getElementById('trip-panel').style.display = 'none';
    document.querySelectorAll('.venue-action-btn.added').forEach(btn => {
        btn.innerHTML = '<i class="fas fa-plus"></i> Trip';
        btn.disabled = false;
        btn.classList.remove('added');
    });
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
}

/**
 * Mark venue cards whose names match items already in the pinned trip.
 */
function markAddedVenues() {
    if (!_pinnedTrip) return;
    const addedNames = new Set(_pinnedItems.map(i => i.title.toLowerCase()));

    document.querySelectorAll('.venue-action-btn.add-to-trip').forEach(btn => {
        try {
            const venue = JSON.parse(btn.dataset.venue);
            if (addedNames.has(venue.name.toLowerCase())) {
                btn.innerHTML = '<i class="fas fa-check"></i> Added';
                btn.disabled = true;
                btn.classList.add('added');
            }
        } catch {}
    });
}

// Close button
document.getElementById('trip-panel-close')?.addEventListener('click', unpinTrip);

// Re-mark venues after new search results are displayed
const _origDisplayVenues = typeof displayVenues === 'function' ? displayVenues : null;
if (_origDisplayVenues) {
    const _real = displayVenues;
    window.displayVenues = function(venues) {
        _real(venues);
        if (_pinnedTrip) markAddedVenues();
    };
}
