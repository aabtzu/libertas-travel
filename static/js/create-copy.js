/* Copy or move an itinerary item / idea to another trip. */

(function () {
    const _cp = new URLSearchParams(window.location.search);
    const _currentLink = _cp.get('link') || _cp.get('edit') || '';

    let _modal = null;
    let _tripList = null;
    let _statusMsg = null;
    let _pendingItem = null;
    let _pendingSource = null; // { type: 'item'|'idea', dayIndex?, itemIndex?, ideaIndex? }

    function _buildModal() {
        if (_modal) return;

        _modal = document.createElement('div');
        _modal.id = 'copy-trip-modal';

        const card = document.createElement('div');
        card.className = 'copy-trip-card';

        const heading = document.createElement('h3');
        heading.id = 'copy-trip-heading';

        const subheading = document.createElement('p');
        subheading.className = 'copy-trip-subheading';
        subheading.textContent = 'Select a trip to copy or move this item to:';

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

        _modal.addEventListener('click', e => {
            if (e.target === _modal) _closeModal();
        });
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') _closeModal();
        });
    }

    function _openModal(item, source) {
        _buildModal();
        _pendingItem = item;
        _pendingSource = source;

        const heading = document.getElementById('copy-trip-heading');
        if (heading) heading.textContent = item.title || 'Item';

        _statusMsg.textContent = '';
        _statusMsg.className = 'copy-trip-status';
        _tripList.textContent = 'Loading trips...';
        _modal.classList.add('is-open');
        _loadTrips();
    }

    function _closeModal() {
        if (_modal) _modal.classList.remove('is-open');
        _pendingItem = null;
        _pendingSource = null;
    }

    async function _loadTrips() {
        try {
            const res = await fetch('/api/trips/list');
            const data = await res.json();
            const currentStem = _currentLink.replace(/\.html$/, '');
            const trips = (data.trips || []).filter(t => {
                const stem = (t.link || '').replace(/\.html$/, '');
                return stem !== currentStem && !t.is_archived;
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

                const copyBtn = _actionButton('Copy', 'copy');
                const moveBtn = _actionButton('Move', 'move');

                copyBtn.addEventListener('click', () => _doAction('copy', t.link, copyBtn, moveBtn));
                moveBtn.addEventListener('click', () => _doAction('move', t.link, copyBtn, moveBtn));

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

    async function _doAction(action, targetLink, copyBtn, moveBtn) {
        if (!_pendingItem) return;
        copyBtn.disabled = true;
        moveBtn.disabled = true;
        _setStatus(action === 'copy' ? 'Copying...' : 'Moving...', 'pending');

        const stem = targetLink.replace(/\.html$/, '');

        try {
            const res = await fetch(`/api/trips/${encodeURIComponent(stem)}/items`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ item: _pendingItem }),
            });
            const data = await res.json();
            if (!res.ok || !data.success) {
                _setStatus(data.error || 'Failed.', 'error');
                copyBtn.disabled = false;
                moveBtn.disabled = false;
                return;
            }

            if (action === 'move') {
                _deleteSource();
            }

            _setStatus(
                action === 'copy' ? 'Item copied to ideas pile.' : 'Item moved to ideas pile.',
                'ok'
            );
            setTimeout(_closeModal, 1200);
        } catch {
            _setStatus('Connection error.', 'error');
            copyBtn.disabled = false;
            moveBtn.disabled = false;
        }
    }

    function _deleteSource() {
        const src = _pendingSource;
        if (!src) return;
        if (src.type === 'item') {
            // deleteItem is defined in create-items.js
            if (typeof deleteItem === 'function') {
                deleteItem(src.dayIndex, src.itemIndex);
            }
        } else if (src.type === 'idea') {
            if (typeof deleteIdea === 'function') {
                deleteIdea(src.ideaIndex);
            }
        }
    }

    // Exposed globally for inline onclick handlers in create-render.js
    window.copyOrMoveItem = function (item, source) {
        _openModal(item, source);
    };
}());
