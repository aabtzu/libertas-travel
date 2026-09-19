/**
 * Polls /api/trips/<link>/heartbeat every 30s and on tab focus.
 * If another user saved the trip since this session loaded, shows a
 * non-blocking banner prompting a reload.
 */

const _HEARTBEAT_INTERVAL_MS = 30000;
let _heartbeatInterval = null;
let _heartbeatBaselineAt = null; // ISO string: the last_saved_at when this session loaded

function initHeartbeat(link) {
    // Fetch baseline (the save timestamp when this session loaded)
    _fetchHeartbeat(link, true);

    // Poll on interval
    _heartbeatInterval = setInterval(() => _fetchHeartbeat(link, false), _HEARTBEAT_INTERVAL_MS);

    // Also poll immediately when the tab becomes visible again (user returns from another tab)
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) _fetchHeartbeat(link, false);
    });
}

function _fetchHeartbeat(link, isBaseline) {
    fetch(`/api/trips/${encodeURIComponent(link)}/heartbeat`)
        .then(r => r.ok ? r.json() : null)
        .then(data => {
            if (!data || !data.last_saved_at) return;
            if (isBaseline) {
                _heartbeatBaselineAt = data.last_saved_at;
                return;
            }
            if (_heartbeatBaselineAt && data.last_saved_at > _heartbeatBaselineAt) {
                _showReloadBanner(data.username || 'Someone');
                // Stop polling once we show the banner; no point re-alerting
                clearInterval(_heartbeatInterval);
            }
        })
        .catch(() => {}); // network errors are silent; heartbeat is best-effort
}

function _showReloadBanner(username) {
    if (document.getElementById('heartbeat-banner')) return; // already shown

    const banner = document.createElement('div');
    banner.id = 'heartbeat-banner';
    banner.className = 'heartbeat-banner';

    const msg = document.createElement('span');
    msg.textContent = `${username} made changes to this trip.`;

    const reloadBtn = document.createElement('button');
    reloadBtn.className = 'heartbeat-reload-btn';
    reloadBtn.textContent = 'Reload to see them';
    reloadBtn.addEventListener('click', () => window.location.reload());

    const dismissBtn = document.createElement('button');
    dismissBtn.className = 'heartbeat-dismiss-btn';
    dismissBtn.textContent = 'Dismiss';
    dismissBtn.setAttribute('aria-label', 'Dismiss notification');
    dismissBtn.addEventListener('click', () => banner.remove());

    banner.appendChild(msg);
    banner.appendChild(reloadBtn);
    banner.appendChild(dismissBtn);
    document.body.appendChild(banner);
}
