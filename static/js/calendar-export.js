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
                <p style="margin-top:0">${copied ? '<i class="fas fa-check" style="color:#43a047"></i> Subscribe URL copied to clipboard.' : 'Copy this URL:'}</p>
                <input type="text" class="modal-input" id="subscribe-url-input" readonly>
                <p style="margin-top:18px; margin-bottom:6px; font-size:0.9rem; color:#333;">
                    Paste it into your calendar app:
                </p>
                <ul class="subscribe-instructions">
                    <li>
                        <strong>Apple Calendar</strong>
                        <span>File &rarr; New Calendar Subscription</span>
                    </li>
                    <li>
                        <strong>Google Calendar</strong>
                        <span>Other calendars + &rarr; From URL</span>
                    </li>
                    <li>
                        <strong>Outlook</strong>
                        <span>Add Calendar &rarr; Subscribe from web</span>
                    </li>
                </ul>
                <p style="font-size:0.8rem; color:#888; margin-top:14px;">
                    The calendar refreshes from this URL automatically as you edit the trip. Or click <strong>Open in calendar</strong> below to hand it to your default app.
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
