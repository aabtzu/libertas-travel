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
    if (!currentShareLink) return;
    closeShareModal();
    window.location.href = '/api/trips/' + encodeURIComponent(currentShareLink) + '/calendar.ics';
}

// Calendar subscribe, fetch a webcal:// URL the user pastes into their
// calendar app. Unlike download, the calendar polls and stays in sync.
async function subscribeTripCalendar() {
    if (!currentShareLink) return;
    try {
        const res = await fetch(
            '/api/trips/' + encodeURIComponent(currentShareLink) + '/calendar-subscribe-url'
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

function _showSubscribeModal(url, copied) {
    closeShareModal();
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal-dialog" style="max-width: 560px;">
            <div class="modal-header">
                <i class="fas fa-rss" style="color: #f0c674; font-size: 1.6rem;"></i>
                <h3>Subscribe to this trip</h3>
            </div>
            <div class="modal-body">
                <p style="margin-top:0">${copied ? 'Subscribe URL copied to clipboard.' : 'Copy this URL:'}</p>
                <input type="text" class="modal-input" id="subscribe-url-input" readonly>
                <p style="font-size:0.85rem; color:#555; line-height:1.5; margin-top:14px;">
                    Paste it into <strong>Outlook</strong> (Add Calendar &rarr; Subscribe from web),
                    <strong>Apple Calendar</strong> (File &rarr; New Calendar Subscription), or
                    <strong>Google Calendar</strong> (Other calendars + &rarr; From URL). The calendar
                    will refresh from this URL automatically as you edit the trip.
                </p>
                <p style="font-size:0.8rem; color:#888;">
                    Some calendar apps also accept clicking the URL directly to open the system
                    calendar app.
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
    input.addEventListener('click', () => input.select());
    overlay.querySelector('#subscribe-url-open').setAttribute('href', url);
}
