/* Copy or move all items from one trip to another. */

(function () {
    let _modal = null;
    let _tripList = null;
    let _statusMsg = null;
    let _sourceLink = null;
    let _sourceTitle = null;
    let _sourceDates = null;

    function _buildModal() {
        if (_modal) return;

        _modal = document.createElement('div');
        _modal.id = 'merge-trip-modal';

        const card = document.createElement('div');
        card.className = 'copy-trip-card';

        const heading = document.createElement('h3');
        heading.id = 'merge-trip-heading';

        const subheading = document.createElement('p');
        subheading.className = 'copy-trip-subheading';

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
        _sourceDates = null;
    }

    function _hasDates(datesStr) {
        return datesStr && datesStr.trim() && datesStr.trim().toLowerCase() !== 'date unknown';
    }

    function _monthYear(datesStr) {
        if (!_hasDates(datesStr)) return null;
        const m = datesStr.match(/([A-Za-z]+)\s+\d+.*?(\d{4})/);
        return m ? m[1] + ' ' + m[2] : null;
    }

    function _openModal(sourceLink, sourceTitle, sourceDates) {
        _buildModal();
        _sourceLink = sourceLink;
        _sourceTitle = sourceTitle;
        _sourceDates = sourceDates || '';

        const heading = document.getElementById('merge-trip-heading');
        if (heading) heading.textContent = sourceTitle || 'this trip';

        const subheading = _modal.querySelector('.copy-trip-subheading');
        if (subheading) {
            subheading.textContent = _hasDates(_sourceDates)
                ? `${_sourceDates} - where do you want to send it?`
                : 'No dates set - items will go to destination ideas pile. Select a destination:';
        }

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

            const sourceHasDates = _hasDates(_sourceDates);

            trips.forEach(t => {
                const wrapper = document.createElement('div');
                wrapper.className = 'copy-trip-wrapper merge-trip-row-wrapper';

                const label = document.createElement('span');
                label.className = 'merge-trip-label';
                label.textContent = t.title || t.link;

                const btnGroup = document.createElement('div');
                btnGroup.className = 'merge-trip-btns';

                if (sourceHasDates) {
                    const itinBtn = _btn('Add to itinerary', 'primary');
                    const ideasBtn = _btn('Add to ideas', 'secondary');

                    itinBtn.title = 'Append days with their dates to the destination trip';
                    ideasBtn.title = 'Strip dates and add all items to the destination ideas pile';

                    itinBtn.addEventListener('click', () => _pickAction('with_dates', t, [itinBtn, ideasBtn]));
                    ideasBtn.addEventListener('click', () => _pickAction('ideas', t, [itinBtn, ideasBtn]));

                    btnGroup.appendChild(itinBtn);
                    btnGroup.appendChild(ideasBtn);
                } else {
                    const copyBtn = _btn('Copy to ideas', 'primary');
                    const moveBtn = _btn('Move to ideas', 'secondary');

                    copyBtn.addEventListener('click', () => _doMerge('copy', 'ideas', t, [copyBtn, moveBtn]));
                    moveBtn.addEventListener('click', () => _doMerge('move', 'ideas', t, [copyBtn, moveBtn]));

                    btnGroup.appendChild(copyBtn);
                    btnGroup.appendChild(moveBtn);
                }

                wrapper.appendChild(label);
                wrapper.appendChild(btnGroup);
                _tripList.appendChild(wrapper);
            });
        } catch {
            _tripList.textContent = 'Error loading trips.';
        }
    }

    function _btn(label, variant) {
        const btn = document.createElement('button');
        btn.textContent = label;
        btn.className = `copy-trip-btn merge-trip-btn--${variant}`;
        return btn;
    }

    function _setStatus(text, state) {
        _statusMsg.textContent = text;
        _statusMsg.className = `copy-trip-status${state ? ' is-' + state : ''}`;
    }

    // For dated trips: show a copy/move choice before executing
    async function _pickAction(mode, targetTrip, btns) {
        const targetTitle = targetTrip.title || targetTrip.link;
        const targetDates = targetTrip.dates || '';

        let description = '';
        if (mode === 'with_dates') {
            description = `Add the days from "${_sourceTitle}" (${_sourceDates}) to "${targetTitle}".`;
            const srcMY = _monthYear(_sourceDates);
            const dstMY = _monthYear(targetDates);
            if (srcMY && dstMY && srcMY !== dstMY) {
                description += `\n\nNote: source is ${srcMY}, destination is ${dstMY}. Days will be appended without renumbering.`;
            }
        } else {
            description = `Add all items from "${_sourceTitle}" to "${targetTitle}" ideas pile (without dates).`;
        }

        // Custom two-action confirm: Copy (keep source) or Move (delete source)
        const action = await _actionDialog(description);
        if (!action) return; // cancelled

        _doMerge(action, mode, targetTrip, btns);
    }

    // Returns 'copy', 'move', or null (cancel)
    function _actionDialog(description) {
        return new Promise(resolve => {
            const overlay = document.createElement('div');
            overlay.className = 'merge-action-overlay';

            const box = document.createElement('div');
            box.className = 'merge-action-box';

            const desc = document.createElement('p');
            desc.className = 'merge-action-desc';
            desc.textContent = description;

            const copyBtn = document.createElement('button');
            copyBtn.textContent = 'Copy (keep original)';
            copyBtn.className = 'copy-trip-btn copy-trip-btn--copy';

            const moveBtn = document.createElement('button');
            moveBtn.textContent = 'Move (delete original)';
            moveBtn.className = 'copy-trip-btn copy-trip-btn--move';

            const cancelBtn = document.createElement('button');
            cancelBtn.textContent = 'Cancel';
            cancelBtn.className = 'copy-trip-cancel';

            function close(result) {
                document.body.removeChild(overlay);
                resolve(result);
            }

            copyBtn.addEventListener('click', () => close('copy'));
            moveBtn.addEventListener('click', () => close('move'));
            cancelBtn.addEventListener('click', () => close(null));
            overlay.addEventListener('click', e => { if (e.target === overlay) close(null); });

            box.appendChild(desc);
            box.appendChild(copyBtn);
            box.appendChild(moveBtn);
            box.appendChild(cancelBtn);
            overlay.appendChild(box);
            document.body.appendChild(overlay);
        });
    }

    async function _doMerge(action, mode, targetTrip, btns) {
        if (btns) btns.forEach(b => { b.disabled = true; });
        _setStatus('Working...', 'pending');

        try {
            const res = await fetch('/api/trips/merge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_link: _sourceLink,
                    target_link: targetTrip.link,
                    action,
                    mode,
                }),
            });
            const data = await res.json();
            if (!res.ok || data.error) {
                _setStatus(data.error || 'Failed.', 'error');
                if (btns) btns.forEach(b => { b.disabled = false; });
                return;
            }

            const count = data.added || 0;
            const what = mode === 'with_dates' ? `${count} item(s) merged` : `${count} item(s) added to ideas`;

            if (action === 'move' && data.deleted_source) {
                _setStatus(`Done - ${what}. Original trip deleted.`, 'ok');
                setTimeout(() => {
                    _closeModal();
                    const sourceStem = (_sourceLink || '').replace(/\.html$/, '');
                    const card = document.querySelector(`.trip-card-wrapper[data-link="${sourceStem}"]`)
                        || document.querySelector(`.trip-card-wrapper[data-link="${_sourceLink}"]`);
                    if (card) card.remove();
                    else window.location.reload();
                }, 1500);
            } else {
                _setStatus(`Done - ${what}.`, 'ok');
                setTimeout(_closeModal, 1500);
            }
        } catch {
            _setStatus('Connection error.', 'error');
            if (btns) btns.forEach(b => { b.disabled = false; });
        }
    }

    window.mergeAllItems = function (sourceLink, sourceTitle, sourceDates) {
        _openModal(sourceLink, sourceTitle, sourceDates);
    };
}());
