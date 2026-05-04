/* Explore Page, Trip picker modal, send-to-trip, add-note flow (split from explore.js) */

function showTripPicker(trips, onSelect) {
    // Remove existing picker
    const old = document.getElementById('trip-picker-modal');
    if (old) old.remove();

    const overlay = document.createElement('div');
    overlay.id = 'trip-picker-modal';
    overlay.className = 'trip-picker-overlay';
    overlay.innerHTML = `
        <div class="trip-picker">
            <div class="trip-picker-header">
                <h3>Add to trip</h3>
                <button class="trip-picker-close" aria-label="Close"><i class="fas fa-times"></i></button>
            </div>
            <p class="trip-picker-note">
                <i class="fas fa-lightbulb"></i>
                Picks land in your trip's <strong>Ideas Pile</strong>, sort them onto specific days later in the editor.
            </p>
            <div class="trip-picker-list">
                <button class="trip-picker-item trip-picker-new" data-action="new">
                    <i class="fas fa-plus-circle"></i>
                    <span>New trip</span>
                </button>
                ${trips.map(t => `
                    <button class="trip-picker-item" data-link="${t.link}">
                        <i class="fas fa-suitcase"></i>
                        <span>${t.title}</span>
                    </button>
                `).join('')}
            </div>
        </div>
    `;

    // Close on overlay click, close button, or Escape
    overlay.addEventListener('click', async (e) => {
        if (e.target === overlay || e.target.closest('.trip-picker-close')) {
            overlay.remove();
            return;
        }
        const item = e.target.closest('.trip-picker-item');
        if (!item) return;

        if (item.dataset.action === 'new') {
            // Send the user to the full Create Trip dialog (one source of
            // truth for new-trip creation, name, dates, OR num_days).
            // Stash the venue + the explore page URL so /create.html can
            // add the venue once the trip exists and offer a way back.
            try {
                if (typeof _pendingVenue !== 'undefined' && _pendingVenue) {
                    sessionStorage.setItem(
                        'libertas_pending_venue',
                        JSON.stringify({
                            venue: _pendingVenue,
                            return_to: window.location.pathname + window.location.search,
                        })
                    );
                }
            } catch { /* sessionStorage may be disabled */ }
            overlay.remove();
            window.location.href = '/create.html';
            return;
        }

        overlay.remove();
        onSelect(item.dataset.link);
    });
    const onEsc = (e) => { if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', onEsc); } };
    document.addEventListener('keydown', onEsc);

    document.body.appendChild(overlay);
}

/**
 * Show an inline note input below the + Trip button before adding.
 */
function showAddNoteInput(btn, venueData) {
    const actionsRow = btn.closest('.venue-card-actions');
    if (!actionsRow || actionsRow.parentElement.querySelector('.add-note-inline')) return;

    // Replace the actions row with the note input
    actionsRow.style.display = 'none';

    const wrapper = document.createElement('div');
    wrapper.className = 'add-note-inline';
    wrapper.innerHTML = `
        <input type="text" class="add-note-input" placeholder="Add a note (optional), Enter to save" >
        <button class="add-note-submit" title="Add"><i class="fas fa-check"></i></button>
        <button class="add-note-cancel" title="Cancel"><i class="fas fa-times"></i></button>
    `;
    actionsRow.parentElement.appendChild(wrapper);

    const input = wrapper.querySelector('input');
    const submitBtn = wrapper.querySelector('.add-note-submit');
    const cancelBtn = wrapper.querySelector('.add-note-cancel');
    input.focus();

    const doCancel = () => {
        wrapper.remove();
        actionsRow.style.display = '';
    };

    const doAdd = async () => {
        const note = input.value.trim();
        wrapper.remove();
        actionsRow.style.display = '';
        await sendToTripWithNote(btn, _pinnedTrip.link, venueData, note);
        if (typeof _pinnedItems !== 'undefined') {
            _pinnedItems.push({
                title: venueData.name,
                category: venueData.venue_type === 'Restaurant' || venueData.venue_type === 'Cafe' ? 'meal' : 'activity',
                location: venueData.city || '',
                notes: note || venueData.cuisine_type || '',
            });
            if (typeof renderTripPanel === 'function') renderTripPanel();
        }
    };

    submitBtn.addEventListener('click', (e) => { e.stopPropagation(); doAdd(); });
    cancelBtn.addEventListener('click', (e) => { e.stopPropagation(); doCancel(); });
    input.addEventListener('keydown', (e) => {
        e.stopPropagation();
        if (e.key === 'Enter') doAdd();
        if (e.key === 'Escape') doCancel();
    });
    input.addEventListener('keyup', (e) => e.stopPropagation());
    input.addEventListener('keypress', (e) => e.stopPropagation());
    input.addEventListener('click', (e) => e.stopPropagation());
}

/**
 * Build a full location string from venue data parts.
 */
function buildVenueLocation(venueData) {
    return [venueData.city, venueData.state, venueData.country].filter(x => x).join(', ');
}

/**
 * Add a venue to a trip. Single function for both with-note and without-note flows.
 */
async function sendToTrip(btn, tripLink, venueData, note) {
    const location = buildVenueLocation(venueData);

    // Build Google Maps link from coordinates or name
    let mapsLink = venueData.google_maps_link || '';
    if (!mapsLink && venueData.latitude && venueData.longitude) {
        mapsLink = `https://www.google.com/maps/search/?api=1&query=${venueData.latitude},${venueData.longitude}`;
    } else if (!mapsLink) {
        const q = encodeURIComponent(`${venueData.name} ${location}`);
        mapsLink = `https://www.google.com/maps/search/?api=1&query=${q}`;
    }

    const item = {
        title: venueData.name,
        category: venueData.venue_type === 'Restaurant' || venueData.venue_type === 'Cafe' ? 'meal' : 'activity',
        location: location,
        latitude: venueData.latitude || null,
        longitude: venueData.longitude || null,
        notes: note || venueData.cuisine_type || '',
        website: venueData.website || '',
        google_maps_link: mapsLink,
    };

    try {
        const res = await fetch(`/api/trips/${tripLink}/items`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({item}),
        });
        if (res.ok) {
            btn.innerHTML = '<i class="fas fa-check"></i> Added';
            btn.disabled = true;
            btn.classList.add('added');
            // Surface a "View trip" link so users discover where the venue went.
            // Without this, adds feel like a black hole on first use.
            const tripTitle = (_tripsCache || []).find(t => t.link === tripLink)?.title || 'trip';
            showAddedToast(venueData.name, tripTitle, tripLink);
        }
    } catch { /* silently fail */ }
}

function showAddedToast(venueName, tripTitle, tripLink) {
    let toast = document.getElementById('explore-added-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'explore-added-toast';
        toast.style.cssText = (
            'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);' +
            'background:#1a1a2e;color:#fff;padding:12px 18px;border-radius:10px;' +
            'box-shadow:0 4px 20px rgba(0,0,0,0.25);z-index:9999;font-size:0.95rem;' +
            'display:flex;align-items:center;gap:14px;max-width:90vw;'
        );
        document.body.appendChild(toast);
    }
    const safeVenue = (venueName || '').replace(/[<>&"]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c]));
    const safeTitle = (tripTitle || '').replace(/[<>&"]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c]));
    toast.innerHTML = (
        `<span><i class="fas fa-check-circle" style="color:#7ed957;margin-right:6px;"></i>` +
        `Added <strong>${safeVenue}</strong> to ${safeTitle}</span>` +
        `<a href="/${encodeURIComponent(tripLink)}" style="color:#a8b4ff;text-decoration:underline;font-weight:600;">View trip</a>`
    );
    toast.style.opacity = '1';
    clearTimeout(showAddedToast._t);
    showAddedToast._t = setTimeout(() => {
        toast.style.transition = 'opacity 0.4s';
        toast.style.opacity = '0';
    }, 5000);
}

// Legacy alias
async function sendToTripWithNote(btn, tripLink, venueData, note) {
    return sendToTrip(btn, tripLink, venueData, note);
}

// Holds the venue currently being added, accessed by the trip-picker's
// "New trip" handler to stash for /create.html before redirecting.
var _pendingVenue = null;  // eslint-disable-line no-unused-vars

async function addToTrip(btn) {
    const venueData = JSON.parse(btn.dataset.venue);
    _pendingVenue = venueData;

    // If a trip is pinned (from explore-trip-panel.js), add directly
    if (typeof _pinnedTrip !== 'undefined' && _pinnedTrip) {
        // Skip if already in this trip
        if (typeof isAlreadyInTrip === 'function' && isAlreadyInTrip(venueData.name)) {
            btn.innerHTML = '<i class="fas fa-check"></i> Added';
            btn.disabled = true;
            btn.classList.add('added');
            return;
        }
        // Show inline note input on the card
        showAddNoteInput(btn, venueData);
        return;
    }

    if (!_tripsCache) {
        try {
            const res = await fetch('/api/trips/list');
            if (res.status === 401) {
                window.location.href = '/login?redirect=/explore.html';
                return;
            }
            const data = await res.json();
            _tripsCache = data.trips || [];
        } catch { return; }
    }

    // Show picker even with 0 trips, "New trip" option is always available
    if (_tripsCache.length === 0) {
        _pendingBtn = btn;
        showTripPicker([], async (link) => {
            await sendToTrip(_pendingBtn, link, venueData);
            const trip = _tripsCache?.find(t => t.link === link);
            if (trip && typeof pinTrip === 'function') pinTrip(link, trip.title);
        });
        return;
    }

    if (_tripsCache.length === 1) {
        await sendToTrip(btn, _tripsCache[0].link, venueData);
        // Auto-pin the single trip
        if (typeof pinTrip === 'function') pinTrip(_tripsCache[0].link, _tripsCache[0].title);
    } else {
        _pendingBtn = btn;
        showTripPicker(_tripsCache, async (link) => {
            await sendToTrip(_pendingBtn, link, venueData);
            // Pin the selected trip
            const trip = _tripsCache.find(t => t.link === link);
            if (trip && typeof pinTrip === 'function') pinTrip(link, trip.title);
        });
    }
}

// Delegate click for add-to-trip buttons
document.addEventListener('click', (e) => {
    const btn = e.target.closest('.add-to-trip');
    if (btn) {
        e.stopPropagation();
        addToTrip(btn);
    }
});

// Export initMap for manual initialization if needed
window.initMap = initMap;
