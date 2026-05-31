/* Libertas - Trip card actions, view toggle, and share modal */

/**
 * Initialize trip card actions (edit, delete, copy).
 *
 * Uses document-level event delegation so cards added later (e.g. clones in
 * list view) get the same behavior without re-binding. Each handler stops
 * propagation so the click doesn't navigate the parent <a> wrapper.
 */
function initTripActions() {
    document.addEventListener('click', (e) => {
        // Edit
        const editBtn = e.target.closest('.edit-btn');
        if (editBtn) {
            e.preventDefault();
            e.stopPropagation();
            editTrip(editBtn);
            return;
        }

        // Delete
        const deleteBtn = e.target.closest('.delete-btn');
        if (deleteBtn) {
            e.preventDefault();
            e.stopPropagation();
            const link = deleteBtn.dataset.link;
            const wrapper = deleteBtn.closest('.trip-card-wrapper');
            const title = wrapper.querySelector('.trip-card-title')?.textContent || 'this trip';
            LibertasModal.confirm(
                `Are you sure you want to delete "${title}"?\n\nThis action cannot be undone.`,
                { danger: true }
            ).then(function(confirmed) {
                if (confirmed) deleteTrip(link, wrapper);
            });
            return;
        }

        // Copy
        const copyBtn = e.target.closest('.copy-btn');
        if (copyBtn) {
            e.preventDefault();
            e.stopPropagation();
            copyTrip(copyBtn.dataset.link);
        }
    });
}

/**
 * Edit a trip - navigate to full editor
 */
function editTrip(btn) {
    const link = btn.dataset.link;
    // Navigate to the full editor
    window.location.href = `/create.html?edit=${link}`;
}

/**
 * Delete a trip
 */
function deleteTrip(link, cardElement) {
    fetch('/api/delete-trip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ link: link })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Animate removal
            cardElement.style.transition = 'opacity 0.3s, transform 0.3s';
            cardElement.style.opacity = '0';
            cardElement.style.transform = 'scale(0.9)';
            setTimeout(() => {
                cardElement.remove();
                showStatus('success', 'Trip deleted successfully');
            }, 300);
        } else {
            showStatus('error', data.error || 'Failed to delete trip');
        }
    })
    .catch(error => {
        console.error('Delete error:', error);
        showStatus('error', 'Failed to delete trip');
    });
}

/**
 * Copy a trip (placeholder for future editor)
 */
function copyTrip(link) {
    fetch('/api/copy-trip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ link: link })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showStatus('success', data.message);
            // Future: Open trip editor with data.trip
        } else {
            showStatus('error', data.error || 'Failed to copy trip');
        }
    })
    .catch(error => {
        console.error('Copy error:', error);
        showStatus('error', 'Failed to copy trip');
    });
}

/**
 * Initialize view toggle (grid/list)
 */
function initViewToggle() {
    const toggleBtns = document.querySelectorAll('.view-toggle-btn');
    const tripsContainer = document.getElementById('trips-container');
    const publicTripsContainer = document.querySelector('.public-trips-grid');

    if (!toggleBtns.length || !tripsContainer) return;

    // Load saved preference
    const savedView = localStorage.getItem('tripsViewMode') || 'grid';
    setView(savedView, tripsContainer, publicTripsContainer, toggleBtns);

    toggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const view = btn.dataset.view;
            setView(view, tripsContainer, publicTripsContainer, toggleBtns);
            localStorage.setItem('tripsViewMode', view);
        });
    });
}

/**
 * Set the view mode
 */
function setView(view, container, publicContainer, buttons) {
    // Update main container class
    container.classList.remove('trips-grid', 'trips-list');
    container.classList.add(view === 'list' ? 'trips-list' : 'trips-grid');

    // Update public trips container class if it exists
    if (publicContainer) {
        publicContainer.classList.remove('trips-grid', 'trips-list');
        publicContainer.classList.add(view === 'list' ? 'trips-list' : 'trips-grid');
    }

    // Update button states
    buttons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });
}

// ==================== Share Modal Functions ====================

// Store current trip being shared
let currentShareLink = '';
let currentShareTitle = '';

/**
 * Open the share modal for a trip
 */
function openShareModal(link, title) {
    currentShareLink = link;
    currentShareTitle = title;

    const modal = document.getElementById('share-modal');
    const titleSpan = document.getElementById('share-trip-title');
    const userList = document.getElementById('user-list');

    if (!modal) return;

    titleSpan.textContent = title;
    userList.innerHTML = '<div class="loading">Loading users...</div>';

    modal.classList.add('show');

    // Load users, build via DOM (no innerHTML interpolation) so a
    // username with quotes / `<script>` can't break out and inject code.
    fetch('/api/users', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            userList.innerHTML = '';
            if (data.success && data.users.length > 0) {
                data.users.forEach(user => {
                    const item = document.createElement('div');
                    item.className = 'user-item';
                    item.dataset.userId = user.id;
                    item.dataset.username = user.username;
                    item.addEventListener('click', () => {
                        shareWithUser(user.id, user.username);
                    });
                    const icon = document.createElement('i');
                    icon.className = 'fas fa-user';
                    const nameSpan = document.createElement('span');
                    nameSpan.className = 'username';
                    nameSpan.textContent = user.username;  // safe
                    item.appendChild(icon);
                    item.appendChild(document.createTextNode(' '));
                    item.appendChild(nameSpan);
                    userList.appendChild(item);
                });
            } else {
                userList.innerHTML = '<div class="loading">No other users available</div>';
            }
        })
        .catch(() => {
            userList.innerHTML = '<div class="loading">Failed to load users</div>';
        });
}

/**
 * Close the share modal
 */
function closeShareModal() {
    const modal = document.getElementById('share-modal');
    if (modal) {
        modal.classList.remove('show');
    }
    currentShareLink = '';
    currentShareTitle = '';
}

/**
 * Share with a specific user
 */
function shareWithUser(userId, username) {
    fetch('/api/share-trip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            link: currentShareLink,
            targetUserId: userId
        })
    })
    .then(response => response.json())
    .then(data => {
        closeShareModal();
        if (data.success) {
            showStatus('success', `Trip shared with ${username}`);
        } else {
            showStatus('error', data.error || 'Failed to share trip');
        }
    })
    .catch(() => {
        closeShareModal();
        showStatus('error', 'Failed to share trip');
    });
}

/**
 * Share with all users
 */
function shareWithAll() {
    fetch('/api/share-trip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            link: currentShareLink,
            shareWithAll: true
        })
    })
    .then(response => response.json())
    .then(data => {
        closeShareModal();
        if (data.success) {
            showStatus('success', data.message || 'Trip shared with all users');
        } else {
            showStatus('error', data.error || 'Failed to share trip');
        }
    })
    .catch(() => {
        closeShareModal();
        showStatus('error', 'Failed to share trip');
    });
}

/**
 * Make trip public (if not already) then call callback with the link.
 */
function _ensurePublicThenCopy(buildUrl) {
    const wrapper = document.querySelector(`.trip-card-wrapper [data-link="${currentShareLink}"]`)
        ?.closest('.trip-card-wrapper');
    const publicBtn = wrapper?.querySelector('.public-btn');
    const isAlreadyPublic = publicBtn?.dataset.public === 'true';

    function doCopy() {
        const url = buildUrl();
        // Copy and open in new tab
        window.open(url, '_blank');
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(url)
                .then(() => { closeShareModal(); })
                .catch(() => { _fallbackCopy(url); });
        } else {
            _fallbackCopy(url);
        }
    }

    function _fallbackCopy(url) {
        const ta = document.createElement('textarea');
        ta.value = url;
        ta.style.cssText = 'position:fixed;opacity:0;';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); } catch(e) {}
        document.body.removeChild(ta);
        closeShareModal();
    }

    if (isAlreadyPublic) {
        doCopy();
    } else {
        fetch('/api/toggle-public', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ link: currentShareLink, isPublic: true })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                if (publicBtn) {
                    publicBtn.dataset.public = 'true';
                    publicBtn.classList.add('active');
                    publicBtn.title = 'Public link, click to make private';
                    publicBtn.innerHTML = '<i class="fas fa-globe"></i>';
                }
                doCopy();
            } else {
                LibertasModal.alert(data.error || 'Failed to make trip public');
            }
        })
        .catch(() => LibertasModal.alert('Failed to make trip public'));
    }
}

function copyItineraryLink() {
    _ensurePublicThenCopy(() => window.location.origin + '/' + currentShareLink);
}

function copyRecommendationLink() {
    const recLink = currentShareLink.replace('.html', '');
    _ensurePublicThenCopy(() => window.location.origin + '/r/' + recLink);
}

function copyWriteupLink() {
    const recLink = currentShareLink.replace('.html', '');
    _ensurePublicThenCopy(() => window.location.origin + '/w/' + recLink);
}

// Calendar download / subscribe live in static/js/calendar-export.js.

// Legacy, used by explore panel
function copyPublicLink() {
    copyRecommendationLink();
}

/**
 * Toggle public visibility of a trip
 */
function togglePublic(btn) {
    const link = btn.dataset.link;
    const isCurrentlyPublic = btn.dataset.public === 'true';
    const newPublicState = !isCurrentlyPublic;

    fetch('/api/toggle-public', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            link: link,
            isPublic: newPublicState
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update button state
            btn.dataset.public = newPublicState ? 'true' : 'false';
            btn.classList.toggle('active', newPublicState);
            btn.title = newPublicState
                ? 'Public link, click to make private'
                : 'Private, click to share via link';
            btn.innerHTML = newPublicState ? '<i class="fas fa-globe"></i>' : '<i class="fas fa-lock"></i>';

            // Update public badge (positioned at top-left of wrapper)
            const wrapper = btn.closest('.trip-card-wrapper');
            let badge = wrapper.querySelector('.public-badge');

            if (newPublicState && !badge) {
                badge = document.createElement('span');
                badge.className = 'public-badge';
                badge.innerHTML = '<i class="fas fa-globe"></i>';
                wrapper.insertBefore(badge, wrapper.firstChild);
            } else if (!newPublicState && badge) {
                badge.remove();
            }

            showStatus('success', data.message);
        } else {
            showStatus('error', data.error || 'Failed to update visibility');
        }
    })
    .catch(() => {
        showStatus('error', 'Failed to update visibility');
    });
}

/**
 * Toggle archived state of a trip. Mirrors togglePublic, they're independent flags.
 */
// toggleArchived() and toggleArchivedSection(), defined in static/js/archive.js

/**
 * Initialize share, public-toggle, and archive-toggle actions.
 *
 * Document-level delegation, works for cards rendered server-side AND for
 * clones that the list view inserts later.
 */
function initShareActions() {
    document.addEventListener('click', (e) => {
        const shareBtn = e.target.closest('.share-btn');
        if (shareBtn) {
            e.preventDefault();
            e.stopPropagation();
            openShareModal(shareBtn.dataset.link, shareBtn.dataset.title);
            return;
        }

        const publicBtn = e.target.closest('.public-btn');
        if (publicBtn) {
            e.preventDefault();
            e.stopPropagation();
            togglePublic(publicBtn);
            return;
        }

        const archiveBtn = e.target.closest('.archive-btn');
        if (archiveBtn) {
            e.preventDefault();
            e.stopPropagation();
            toggleArchived(archiveBtn);
        }
    });

    // Close modal when clicking outside
    const modal = document.getElementById('share-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeShareModal();
            }
        });
    }

    // Close modal on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeShareModal();
        }
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initTripActions();
    initViewToggle();
    initShareActions();
});
