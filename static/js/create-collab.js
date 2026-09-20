/* Collaborator panel: invite by email, list current collaborators, remove. */
/* Share button shown to any editor. Remove buttons shown only to the trip owner. */

(function () {
    const collabBtn = document.getElementById('collab-btn');
    const collabPanel = document.getElementById('collab-panel');
    const collabList = document.getElementById('collab-list');
    const collabEmailInput = document.getElementById('collab-email-input');
    const collabInviteBtn = document.getElementById('collab-invite-btn');
    const collabMsg = document.getElementById('collab-msg');

    if (!collabBtn) return;

    const link = new URLSearchParams(window.location.search).get('link') || '';

    function _msg(text, ok) {
        collabMsg.textContent = text;
        collabMsg.style.color = ok ? 'var(--status-success)' : 'var(--status-error)';
    }

    async function loadCollaborators() {
        collabList.textContent = 'Loading...';
        try {
            const res = await fetch(`/api/trips/${encodeURIComponent(link)}/collaborators`);
            if (!res.ok) {
                collabList.textContent = '';
                return;
            }
            const data = await res.json();
            const collabs = data.collaborators || [];
            if (!collabs.length) {
                collabList.innerHTML = '<span style="color:#888;">No collaborators yet.</span>';
                return;
            }
            collabList.innerHTML = '';
            collabs.forEach(c => {
                const row = document.createElement('div');
                row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;';

                const label = document.createElement('span');
                label.style.fontSize = '13px';
                if (c.username) {
                    label.textContent = c.username + ' ';
                    const sub = document.createElement('span');
                    sub.style.color = '#888';
                    sub.textContent = `(${c.email})`;
                    label.appendChild(sub);
                } else {
                    label.style.color = '#888';
                    label.textContent = `${c.email} - pending`;
                }

                const removeBtn = document.createElement('button');
                removeBtn.dataset.id = c.id;
                removeBtn.className = 'collab-remove-btn';
                removeBtn.style.cssText = 'background:none;border:none;color:var(--status-error);cursor:pointer;font-size:12px;';
                removeBtn.textContent = 'Remove';
                // Only the trip owner can remove collaborators
                if (!window._isOwner) removeBtn.style.display = 'none';

                row.appendChild(label);
                row.appendChild(removeBtn);
                collabList.appendChild(row);
            });

            collabList.querySelectorAll('.collab-remove-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const cid = btn.dataset.id;
                    btn.disabled = true;
                    const r = await fetch(
                        `/api/trips/${encodeURIComponent(link)}/collaborators/${cid}`,
                        { method: 'DELETE' }
                    );
                    if (r.ok) {
                        loadCollaborators();
                    } else {
                        _msg('Failed to remove', false);
                        btn.disabled = false;
                    }
                });
            });
        } catch {
            collabList.innerHTML = '<span style="color:var(--status-error);">Error loading collaborators.</span>';
        }
    }

    async function sendInvite() {
        const email = collabEmailInput.value.trim();
        if (!email) return;
        collabInviteBtn.disabled = true;
        _msg('', true);
        try {
            const res = await fetch(`/api/trips/${encodeURIComponent(link)}/invite`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            });
            const data = await res.json();
            if (res.ok && data.success) {
                collabEmailInput.value = '';
                _msg(data.pending ? 'Invite sent.' : 'Invite sent and accepted.', true);
                loadCollaborators();
            } else {
                _msg(data.error || 'Failed to send invite', false);
            }
        } catch {
            _msg('Connection error', false);
        }
        collabInviteBtn.disabled = false;
    }

    collabInviteBtn.addEventListener('click', sendInvite);
    collabEmailInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') sendInvite();
    });

    // Toggle panel open/close
    collabBtn.addEventListener('click', e => {
        e.stopPropagation();
        const open = collabPanel.style.display === 'none' || collabPanel.style.display === '';
        collabPanel.style.display = open ? 'block' : 'none';
        if (open) {
            loadCollaborators();
            collabEmailInput.focus();
        }
    });

    // Close panel on outside click
    document.addEventListener('click', e => {
        if (!collabPanel.contains(e.target) && e.target !== collabBtn) {
            collabPanel.style.display = 'none';
        }
    });

    // Show the Share button to any editor (owner or collaborator).
    // create.js sets window._canEdit after the can-edit check resolves.
    // We poll briefly because scripts load in parallel.
    function showIfEditor() {
        if (typeof window._canEdit !== 'undefined') {
            collabBtn.style.display = window._canEdit ? '' : 'none';
        } else {
            setTimeout(showIfEditor, 200);
        }
    }
    showIfEditor();
}());
