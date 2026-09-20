/* Copy or move an itinerary item / idea to another trip. */

(function () {
    const _currentLink = new URLSearchParams(window.location.search).get('link') || '';

    let _modal = null;
    let _tripList = null;
    let _statusMsg = null;
    let _pendingItem = null;
    let _pendingSource = null; // { type: 'item'|'idea', dayIndex?, itemIndex?, ideaIndex? }

    function _buildModal() {
        if (_modal) return;

        _modal = document.createElement('div');
        _modal.id = 'copy-trip-modal';
        _modal.style.cssText = [
            'display:none',
            'position:fixed',
            'inset:0',
            'z-index:2000',
            'background:rgba(0,0,0,0.5)',
            'align-items:center',
            'justify-content:center',
        ].join(';');

        const card = document.createElement('div');
        card.style.cssText = [
            'background:#fff',
            'border-radius:12px',
            'padding:24px',
            'width:400px',
            'max-width:90vw',
            'max-height:80vh',
            'overflow-y:auto',
            'box-shadow:0 8px 32px rgba(0,0,0,0.18)',
        ].join(';');

        const heading = document.createElement('h3');
        heading.id = 'copy-trip-heading';
        heading.style.cssText = 'margin:0 0 4px;font-size:16px;color:#1a1a2e;';

        const subheading = document.createElement('p');
        subheading.style.cssText = 'margin:0 0 16px;font-size:13px;color:#888;';
        subheading.textContent = 'Select a trip to copy or move this item to:';

        _tripList = document.createElement('div');
        _tripList.style.cssText = 'display:flex;flex-direction:column;gap:8px;margin-bottom:12px;';

        _statusMsg = document.createElement('div');
        _statusMsg.style.cssText = 'font-size:13px;min-height:18px;';

        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = 'Cancel';
        cancelBtn.style.cssText = [
            'margin-top:12px',
            'padding:8px 16px',
            'border:1px solid #ddd',
            'border-radius:6px',
            'background:#fff',
            'cursor:pointer',
            'font-size:13px',
        ].join(';');
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
        _tripList.textContent = 'Loading trips...';
        _modal.style.display = 'flex';
        _loadTrips();
    }

    function _closeModal() {
        if (_modal) _modal.style.display = 'none';
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
                row.style.cssText = 'display:flex;gap:8px;align-items:center;';

                const label = document.createElement('span');
                label.style.cssText = 'flex:1;font-size:14px;color:#1a1a2e;padding:10px 0;';
                label.textContent = t.title || t.link;

                const copyBtn = _actionButton('Copy', '#667eea');
                const moveBtn = _actionButton('Move', '#e74c3c');

                copyBtn.addEventListener('click', () => _doAction('copy', t.link, copyBtn, moveBtn));
                moveBtn.addEventListener('click', () => _doAction('move', t.link, copyBtn, moveBtn));

                row.appendChild(label);
                row.appendChild(copyBtn);
                row.appendChild(moveBtn);

                const wrapper = document.createElement('div');
                wrapper.style.cssText = 'border:1px solid #e0e0e0;border-radius:8px;padding:4px 12px;background:#f8f9fa;transition:border-color 0.15s;';
                wrapper.addEventListener('mouseenter', () => { wrapper.style.borderColor = '#667eea'; });
                wrapper.addEventListener('mouseleave', () => { wrapper.style.borderColor = '#e0e0e0'; });
                wrapper.appendChild(row);
                _tripList.appendChild(wrapper);
            });
        } catch {
            _tripList.textContent = 'Error loading trips.';
        }
    }

    const _HOVER_DARKEN = { '#667eea': '#5a6fd6', '#e74c3c': '#c0392b' };

    function _actionButton(label, color) {
        const btn = document.createElement('button');
        btn.textContent = label;
        btn.style.cssText = [
            `background:${color}`,
            'color:#fff',
            'border:none',
            'border-radius:6px',
            'padding:6px 14px',
            'font-size:13px',
            'cursor:pointer',
        ].join(';');
        const hoverColor = _HOVER_DARKEN[color] || color;
        btn.addEventListener('mouseenter', () => { btn.style.background = hoverColor; });
        btn.addEventListener('mouseleave', () => { btn.style.background = color; });
        return btn;
    }

    async function _doAction(action, targetLink, copyBtn, moveBtn) {
        if (!_pendingItem) return;
        copyBtn.disabled = true;
        moveBtn.disabled = true;
        _statusMsg.style.color = '#888';
        _statusMsg.textContent = action === 'copy' ? 'Copying...' : 'Moving...';

        const stem = targetLink.replace(/\.html$/, '');

        try {
            const res = await fetch(`/api/trips/${encodeURIComponent(stem)}/items`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ item: _pendingItem }),
            });
            const data = await res.json();
            if (!res.ok || !data.success) {
                _statusMsg.style.color = '#e74c3c';
                _statusMsg.textContent = data.error || 'Failed.';
                copyBtn.disabled = false;
                moveBtn.disabled = false;
                return;
            }

            if (action === 'move') {
                _deleteSource();
            }

            _statusMsg.style.color = '#27ae60';
            _statusMsg.textContent = action === 'copy'
                ? 'Item copied to ideas pile.'
                : 'Item moved to ideas pile.';
            setTimeout(_closeModal, 1200);
        } catch {
            _statusMsg.style.color = '#e74c3c';
            _statusMsg.textContent = 'Connection error.';
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
