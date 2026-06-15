/**
 * Calendar export buttons in the share modal.
 *
 * Two flows:
 *   - downloadTripIcs(): one-shot snapshot, calendar app imports as static.
 *   - subscribeTripCalendar(): fetches a webcal:// URL with a token. Calendar
 *     apps poll that URL on their own schedule and stay in sync with edits.
 *
 * Depends on globals from upload.js: currentShareLink, closeShareModal.
 * Split from upload.js when that file crossed the 800-line hard limit
 * (issue #59 tracks further upload.js cleanup).
 */

// Calendar export, downloads an .ics with a snapshot of the trip.
// Calendar apps (Outlook, Apple, Google) consume the same format.
function downloadTripIcs() {
    // Capture the link before closeShareModal() resets currentShareLink to ''.
    // Without the local copy, the URL becomes /api/trips//calendar.ics and 404s.
    const link = currentShareLink;
    if (!link) return;
    closeShareModal();
    window.location.href = '/api/trips/' + encodeURIComponent(link) + '/calendar.ics';
}

// Calendar subscribe, fetch a webcal:// URL the user pastes into their
// calendar app. Unlike download, the calendar polls and stays in sync.
async function subscribeTripCalendar() {
    const link = currentShareLink;
    if (!link) return;
    try {
        const res = await fetch(
            '/api/trips/' + encodeURIComponent(link) + '/calendar-subscribe-url'
        );
        if (!res.ok) {
            alert('Could not generate subscribe URL. Try again.');
            return;
        }
        const data = await res.json();
        const url = data.url || '';
        if (!url) return;
        // Try to copy to clipboard so the user can paste into Outlook/Apple/Google.
        // Some browsers also let webcal:// URLs open the system calendar app
        // directly; we offer both paths.
        try {
            await navigator.clipboard.writeText(url);
            _showSubscribeModal(url, true);
        } catch {
            _showSubscribeModal(url, false);
        }
    } catch (e) {
        alert('Could not generate subscribe URL: ' + e.message);
    }
}

// All-trips feed: single webcal:// URL covering every published trip with dates.
// Shown from a button on the trips page header (not the share modal).
async function subscribeAllTripsCalendar() {
    try {
        const res = await fetch('/api/calendar/subscribe-url');
        if (!res.ok) {
            alert('Could not generate calendar URL. Try again.');
            return;
        }
        const data = await res.json();
        const url = data.url || '';
        if (!url) return;
        try {
            await navigator.clipboard.writeText(url);
            _showSubscribeModal(url, true, 'Subscribe to all trips');
        } catch {
            _showSubscribeModal(url, false, 'Subscribe to all trips');
        }
    } catch (e) {
        alert('Could not generate calendar URL: ' + e.message);
    }
}

function _showSubscribeModal(url, copied, title) {
    // closeShareModal is defined in upload.js; only call it when the share modal is open.
    if (typeof closeShareModal === 'function') closeShareModal();
    // Google Calendar fetches from their servers and works better with https://.
    // Apple Calendar and Outlook both handle webcal:// natively.
    const httpsUrl = url.replace(/^webcal:\/\//, 'https://');
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal-dialog" style="max-width: 560px;">
            <div class="modal-header">
                <i class="fas fa-rss" style="color: #f0c674; font-size: 1.6rem;"></i>
                <h3>${title || 'Subscribe to this trip'}</h3>
            </div>
            <div class="modal-body">
                <p style="margin-top:0">${copied ? '<i class="fas fa-check" style="color:#43a047"></i> Copied to clipboard.' : 'Copy this URL:'}</p>
                <input type="text" class="modal-input" id="subscribe-url-input" readonly>
                <ul class="subscribe-instructions" style="margin-top:18px;">
                    <li>
                        <strong>Apple Calendar</strong>
                        <span>File &rarr; New Calendar Subscription &rarr; paste above</span>
                    </li>
                    <li>
                        <strong>Google Calendar</strong>
                        <span>Other calendars + &rarr; From URL &rarr; paste the URL below</span>
                    </li>
                    <li>
                        <strong>Outlook</strong>
                        <span>Add Calendar &rarr; Subscribe from web &rarr; paste above</span>
                    </li>
                </ul>
                <input type="text" class="modal-input" id="subscribe-url-https" readonly style="margin-top:8px; font-size:0.8rem;">
                <p style="font-size:0.75rem; color:#888; margin-top:6px; margin-bottom:0;">
                    Google Calendar URL (https://)
                </p>
            </div>
            <div class="modal-footer">
                <a id="subscribe-url-open" class="modal-btn modal-btn-secondary">Open in calendar</a>
                <button class="modal-btn modal-btn-primary" onclick="this.closest('.modal-overlay').remove()">Done</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    const input = overlay.querySelector('#subscribe-url-input');
    input.value = url;
    input.addEventListener('click', () => { input.select(); navigator.clipboard.writeText(url).catch(() => {}); });
    const httpsInput = overlay.querySelector('#subscribe-url-https');
    httpsInput.value = httpsUrl;
    httpsInput.addEventListener('click', () => { httpsInput.select(); navigator.clipboard.writeText(httpsUrl).catch(() => {}); });
    overlay.querySelector('#subscribe-url-open').setAttribute('href', url);
}
