/* Copy or move all items from one trip to another. */

(function () {
    let _modal = null;
    let _tripList = null;
    let _statusMsg = null;
    let _sourceLink = null;
    let _sourceTitle = null;

    function _buildModal() {
        if (_modal) return;

        _modal = document.createElement('div');
        _modal.id = 'merge-trip-modal';

        const card = document.createElement('div');
        card.className = 'copy-trip-card';

        const heading = document.createElement('h3');
        heading.id = 'merge-trip-heading';
        heading.textContent = 'Copy or move all items';

        const subheading = document.createElement('p');
        subheading.className = 'copy-trip-subheading';
        subheading.textContent = 'Select a destination trip:';

        _tripList = document.createElement('div');
        _tripList.className = 'copy-trip-list';

        _statusMsg = document.createElement('div');
        _statusMsg.className = 'copy-trip-status';

        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = 'Cancel';
        cancelBtn.className = 'copy-trip-cancel';
        cancelBtn.addEventListener('click', _closeModal);

        card.appendChild(heading);
        card.appendChild(subheading);
        card.appendChild(_tripList);
        card.appendChild(_statusMsg);
        card.appendChild(cancelBtn);
        _modal.appendChild(card);
        document.body.appendChild(_modal);

        _modal.addEventListener('click', e => { if (e.target === _modal) _closeModal(); });
        document.addEventListener('keydown', e => { if (e.key === 'Escape') _closeModal(); });
    }

    function _closeModal() {
        if (_modal) _modal.classList.remove('is-open');
        _sourceLink = null;
        _sourceTitle = null;
    }

    function _openModal(sourceLink, sourceTitle) {
        _buildModal();
        _sourceLink = sourceLink;
        _sourceTitle = sourceTitle;
        _statusMsg.textContent = '';
        _statusMsg.className = 'copy-trip-status';
        _tripList.textContent = 'Loading trips...';
        _modal.classList.add('is-open');
        _loadTrips();
    }

    async function _loadTrips() {
        try {
            const res = await fetch('/api/trips/list');
            const data = await res.json();
            const sourceStem = (_sourceLink || '').replace(/\.html$/, '');
            const trips = (data.trips || []).filter(t => {
                const stem = (t.link || '').replace(/\.html$/, '');
                return stem !== sourceStem && !t.is_archived;
            });

            _tripList.innerHTML = '';
            if (!trips.length) {
                _tripList.textContent = 'No other trips found.';
                return;
            }

            trips.forEach(t => {
                const row = document.createElement('div');
                row.className = 'copy-trip-row';

                const label = document.createElement('span');
                label.className = 'copy-trip-label';
                label.textContent = t.title || t.link;

                const copyBtn = _actionButton('Copy all', 'copy');
                const moveBtn = _actionButton('Move all', 'move');

                copyBtn.addEventListener('click', () => _doMerge('copy', t.link, t.title, copyBtn, moveBtn));
                moveBtn.addEventListener('click', () => _doMerge('move', t.link, t.title, copyBtn, moveBtn));

                row.appendChild(label);
                row.appendChild(copyBtn);
                row.appendChild(moveBtn);

                const wrapper = document.createElement('div');
                wrapper.className = 'copy-trip-wrapper';
                wrapper.appendChild(row);
                _tripList.appendChild(wrapper);
            });
        } catch {
            _tripList.textContent = 'Error loading trips.';
        }
    }

    function _actionButton(label, variant) {
        const btn = document.createElement('button');
        btn.textContent = label;
        btn.className = `copy-trip-btn copy-trip-btn--${variant}`;
        return btn;
    }

    function _setStatus(text, state) {
        _statusMsg.textContent = text;
        _statusMsg.className = `copy-trip-status${state ? ' is-' + state : ''}`;
    }

    async function _doMerge(action, targetLink, targetTitle, copyBtn, moveBtn) {
        const confirmMsg = action === 'move'
            ? `Move all items from "${_sourceTitle}" to "${targetTitle}"?\n\nThe source trip will be deleted after the move.`
            : `Copy all items from "${_sourceTitle}" to "${targetTitle}"?`;

        const confirmed = await LibertasModal.confirm(confirmMsg, { danger: action === 'move' });
        if (!confirmed) return;

        copyBtn.disabled = true;
        moveBtn.disabled = true;
        _setStatus(action === 'copy' ? 'Copying...' : 'Moving...', 'pending');

        try {
            const res = await fetch('/api/trips/merge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_link: _sourceLink,
                    target_link: targetLink,
                    action,
                }),
            });
            const data = await res.json();
            if (!res.ok || !data.success) {
                _setStatus(data.error || 'Failed.', 'error');
                copyBtn.disabled = false;
                moveBtn.disabled = false;
                return;
            }

            const count = data.added || 0;
            if (action === 'move' && data.deleted_source) {
                _setStatus(`Moved ${count} item(s). Source trip deleted.`, 'ok');
                setTimeout(() => {
                    _closeModal();
                    // Remove card from the trips list if present
                    const sourceStem = (_sourceLink || '').replace(/\.html$/, '');
                    const card = document.querySelector(`.trip-card-wrapper[data-link="${sourceStem}"]`)
                        || document.querySelector(`.trip-card-wrapper[data-link="${_sourceLink}"]`);
                    if (card) card.remove();
                    else window.location.reload();
                }, 1500);
            } else {
                _setStatus(`${count} item(s) copied to ideas pile.`, 'ok');
                setTimeout(_closeModal, 1500);
            }
        } catch {
            _setStatus('Connection error.', 'error');
            copyBtn.disabled = false;
            moveBtn.disabled = false;
        }
    }

    // Exposed so trip card buttons and trips-actions.js can open it
    window.mergeAllItems = function (sourceLink, sourceTitle) {
        _openModal(sourceLink, sourceTitle);
    };
}());
