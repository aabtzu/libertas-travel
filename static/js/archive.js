/**
 * Trip archive controls, toggle archive state on a trip card and
 * show/hide the archived-trips section.
 *
 * The archive button click is wired up by initShareActions in upload.js
 * via document-level event delegation, which calls toggleArchived().
 * showStatus() is also defined in upload.js.
 */

function toggleArchived(btn) {
    const link = btn.dataset.link;
    const isCurrentlyArchived = btn.dataset.archived === 'true';
    const newArchivedState = !isCurrentlyArchived;

    fetch('/api/toggle-archived', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ link: link, isArchived: newArchivedState })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Move the card between active and archived sections without a full reload
            // a reload would lose the user's "Show archived" state and is jarring on long lists.
            const wrapper = btn.closest('.trip-card-wrapper');
            wrapper.dataset.isArchived = newArchivedState ? 'true' : 'false';
            wrapper.classList.toggle('is-archived', newArchivedState);
            btn.dataset.archived = newArchivedState ? 'true' : 'false';
            btn.classList.toggle('active', newArchivedState);
            btn.title = newArchivedState ? 'Unarchive trip' : 'Archive trip';

            // Add/remove badge
            let badge = wrapper.querySelector('.archived-badge');
            if (newArchivedState && !badge) {
                badge = document.createElement('span');
                badge.className = 'archived-badge';
                badge.innerHTML = '<i class="fas fa-box-archive"></i> Archived';
                wrapper.insertBefore(badge, wrapper.firstChild);
            } else if (!newArchivedState && badge) {
                badge.remove();
            }

            // Move the card to the right grid. The archived section's inner
            // container alternates between .trips-grid (cards view) and
            // .trips-list (list view), match either.
            const archivedSection = document.getElementById('archived-section');
            const archivedGrid = archivedSection?.querySelector(
                '.trips-grid, .trips-list'
            );
            const activeGrid = document.getElementById('trips-container');
            if (newArchivedState && archivedGrid) {
                archivedGrid.appendChild(wrapper);
            } else if (!newArchivedState && activeGrid) {
                activeGrid.appendChild(wrapper);
            }

            // Update the "Show archived (N)" toggle button, show it once
            // there's at least one archived trip, hide when count drops to 0.
            const toggleBtn = document.getElementById('show-archived-btn');
            const archivedCount = archivedGrid ? archivedGrid.querySelectorAll('.trip-card-wrapper').length : 0;
            if (toggleBtn) {
                if (archivedCount > 0) {
                    toggleBtn.removeAttribute('hidden');
                } else {
                    toggleBtn.setAttribute('hidden', '');
                    // Section also hides when nothing's archived
                    if (archivedSection) archivedSection.setAttribute('hidden', '');
                }
                const label = toggleBtn.querySelector('.archived-toggle-label');
                if (label) {
                    const isExpanded = archivedSection && !archivedSection.hasAttribute('hidden');
                    label.textContent = isExpanded
                        ? 'Hide archived'
                        : `Show archived (${archivedCount})`;
                }
            }

            showStatus('success', data.message);
        } else {
            showStatus('error', data.error || 'Failed to update archive state');
        }
    })
    .catch(() => showStatus('error', 'Failed to update archive state'));
}

/**
 * Toggle visibility of the archived trips section.
 */
function toggleArchivedSection() {
    const section = document.getElementById('archived-section');
    const btn = document.getElementById('show-archived-btn');
    if (!section || !btn) return;

    const label = btn.querySelector('.archived-toggle-label');
    const isHidden = section.hasAttribute('hidden');
    if (isHidden) {
        section.removeAttribute('hidden');
        if (label) label.textContent = 'Hide archived';
    } else {
        section.setAttribute('hidden', '');
        const count = section.querySelectorAll('.trip-card-wrapper').length;
        if (label) label.textContent = `Show archived (${count})`;
    }
}

// Exposed for inline onclick="toggleArchivedSection()" on the toggle button
window.toggleArchivedSection = toggleArchivedSection;
