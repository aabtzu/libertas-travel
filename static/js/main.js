/* Libertas - Main JavaScript */

/**
 * Shared category→icon and category→color maps.
 * Single source of truth, used by create.js, create-grid.js, create-map.js,
 * trip.js, item-detail.js, and calendar.js. Change here; nowhere else.
 */
const CATEGORY_ICONS = {
    'travel':     'fa-plane',
    'flight':     'fa-plane',
    'transport':  'fa-car',
    'train':      'fa-train',
    'bus':        'fa-bus',
    'hotel':      'fa-bed',
    'lodging':    'fa-bed',
    'meal':       'fa-utensils',
    'restaurant': 'fa-utensils',
    'activity':   'fa-star',
    'attraction': 'fa-landmark',
    'other':      'fa-calendar-day'
};

const CATEGORY_COLORS = {
    'flight':     '#3b82f6',
    'transport':  '#f59e0b',
    'train':      '#f59e0b',
    'bus':        '#f59e0b',
    'hotel':      '#8b5cf6',
    'lodging':    '#8b5cf6',
    'meal':       '#ef4444',
    'activity':   '#22c55e',
    'attraction': '#06b6d4',
    'other':      '#6b7280'
};

/**
 * Shared file upload validation, single source of truth for allowed types.
 * Used by both the trips page upload widget (upload.js) and the create page (create.js).
 */
const LibertasUpload = {
    ALLOWED_EXTENSIONS: ['.pdf', '.txt', '.png', '.jpg', '.jpeg', '.html', '.htm', '.eml', '.ics', '.json', '.xlsx', '.xls', '.docx'],
    ACCEPT_ATTR: '.pdf,.txt,.png,.jpg,.jpeg,.html,.htm,.eml,.ics,.json,.xlsx,.xls,.docx',
    DESCRIPTION: 'PDF, Word (docx), images (PNG, JPG), text, HTML, email, calendar (ICS), JSON, Excel',

    isAllowed: function(filename) {
        const lower = filename.toLowerCase();
        return this.ALLOWED_EXTENSIONS.some(ext => lower.endsWith(ext));
    },
};

/**
 * Shared chat utilities - input history and cancel support
 */
const LibertasChat = {
    // Per-instance state stored by input element ID
    instances: {},

    /**
     * Initialize chat input with history and cancel support
     * @param {Object} config - Configuration object
     * @param {string} config.inputId - ID of the input/textarea element
     * @param {string} config.sendBtnId - ID of the send button
     * @param {Function} config.onSend - Callback when message is sent, receives (message, abortController)
     * @param {Function} [config.onCancel] - Optional callback when request is cancelled
     * @returns {Object} Chat instance with cancel() method
     */
    init: function(config) {
        const input = document.getElementById(config.inputId);
        const sendBtn = document.getElementById(config.sendBtnId);

        if (!input || !sendBtn) {
            console.warn('LibertasChat: Could not find input or send button');
            return null;
        }

        // Initialize instance state
        const instance = {
            history: [],
            historyIndex: -1,
            currentInput: '',
            abortController: null,
            isLoading: false,
            originalBtnHtml: sendBtn.innerHTML
        };

        this.instances[config.inputId] = instance;

        // Send message handler
        const sendMessage = async () => {
            const message = input.value.trim();
            if (!message || instance.isLoading) return;

            // Add to history (avoid duplicates)
            if (instance.history[instance.history.length - 1] !== message) {
                instance.history.push(message);
                // Keep last 50 messages
                if (instance.history.length > 50) {
                    instance.history.shift();
                }
            }
            instance.historyIndex = instance.history.length;
            instance.currentInput = '';

            // Create abort controller for this request
            instance.abortController = new AbortController();
            instance.isLoading = true;

            // Update button to show cancel
            sendBtn.innerHTML = '<i class="fas fa-stop"></i>';
            sendBtn.title = 'Cancel request';
            sendBtn.classList.add('cancel-mode');

            try {
                await config.onSend(message, instance.abortController);
            } catch (error) {
                if (error.name === 'AbortError') {
                    console.log('Request cancelled by user');
                    if (config.onCancel) config.onCancel();
                } else {
                    throw error;
                }
            } finally {
                instance.isLoading = false;
                instance.abortController = null;
                sendBtn.innerHTML = instance.originalBtnHtml;
                sendBtn.title = 'Send message';
                sendBtn.classList.remove('cancel-mode');
            }
        };

        // Cancel handler
        const cancelRequest = () => {
            if (instance.abortController) {
                instance.abortController.abort();
            }
        };

        // Button click - send or cancel
        sendBtn.addEventListener('click', () => {
            if (instance.isLoading) {
                cancelRequest();
            } else {
                sendMessage();
            }
        });

        // Keyboard handling
        input.addEventListener('keydown', (e) => {
            // Enter to send (without shift)
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!instance.isLoading) {
                    sendMessage();
                }
                return;
            }

            // Escape to cancel
            if (e.key === 'Escape' && instance.isLoading) {
                e.preventDefault();
                cancelRequest();
                return;
            }

            // Up arrow for history
            if (e.key === 'ArrowUp' && input.selectionStart === 0) {
                e.preventDefault();
                if (instance.history.length === 0) return;

                // Save current input if starting to browse history
                if (instance.historyIndex === instance.history.length) {
                    instance.currentInput = input.value;
                }

                if (instance.historyIndex > 0) {
                    instance.historyIndex--;
                    input.value = instance.history[instance.historyIndex];
                    // Move cursor to end
                    setTimeout(() => input.setSelectionRange(input.value.length, input.value.length), 0);
                }
                return;
            }

            // Down arrow for history
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (instance.historyIndex < instance.history.length - 1) {
                    instance.historyIndex++;
                    input.value = instance.history[instance.historyIndex];
                } else if (instance.historyIndex === instance.history.length - 1) {
                    instance.historyIndex = instance.history.length;
                    input.value = instance.currentInput;
                }
                // Move cursor to end
                setTimeout(() => input.setSelectionRange(input.value.length, input.value.length), 0);
                return;
            }
        });

        // Auto-resize textarea
        input.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 120) + 'px';
            // Reset history index when typing
            instance.historyIndex = instance.history.length;
        });

        // Return instance methods
        return {
            cancel: cancelRequest,
            isLoading: () => instance.isLoading,
            getHistory: () => [...instance.history]
        };
    }
};

/**
 * Shared map configuration - single source of truth for all maps
 */
const LibertasMap = {
    // Tile layer configuration
    tiles: {
        url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
        options: {
            subdomains: 'abcd',
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
        }
    },

    /**
     * Add the standard tile layer to a Leaflet map
     * @param {L.Map} map - The Leaflet map instance
     * @returns {L.TileLayer} The tile layer that was added
     */
    addTileLayer: function(map) {
        return L.tileLayer(this.tiles.url, this.tiles.options).addTo(map);
    },

    /**
     * Create a new Leaflet map with standard tiles
     * @param {string|HTMLElement} container - The container element or ID
     * @param {Object} options - Leaflet map options (center, zoom, etc.)
     * @returns {L.Map} The created map instance
     */
    create: function(container, options) {
        const map = L.map(container, options);
        this.addTileLayer(map);
        return map;
    }
};

/**
 * Switch between tabs on the trip view page
 * @param {string} tabName - The name of the tab to switch to ('summary' or 'map')
 */
function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    event.currentTarget.classList.add('active');

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(tabName + '-tab').classList.add('active');
}

/**
 * Initialize a mobile sidebar with FAB toggle
 * @param {Object} config - Configuration object
 * @param {string} config.sidebarId - ID of the sidebar element
 * @param {string} config.fabId - ID of the FAB button element
 * @param {string} config.overlayId - ID of the overlay element
 * @param {string} config.closeBtnId - ID of the close button element
 */
function initMobileSidebar(config) {
    const sidebar = document.getElementById(config.sidebarId);
    const fab = document.getElementById(config.fabId);
    const overlay = document.getElementById(config.overlayId);
    const closeBtn = document.getElementById(config.closeBtnId);

    if (!sidebar || !fab) return;

    function openSidebar() {
        sidebar.classList.add('open');
        overlay?.classList.add('visible');
        fab.classList.add('hidden');
        document.body.classList.add('sidebar-open');
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        overlay?.classList.remove('visible');
        fab.classList.remove('hidden');
        document.body.classList.remove('sidebar-open');
    }

    fab.addEventListener('click', openSidebar);
    closeBtn?.addEventListener('click', closeSidebar);
    overlay?.addEventListener('click', closeSidebar);

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && sidebar.classList.contains('open')) {
            closeSidebar();
        }
    });

    return { open: openSidebar, close: closeSidebar };
}

/**
 * Initialize mobile navigation hamburger menu
 */
function initMobileNav() {
    const hamburger = document.getElementById('nav-hamburger');
    const navLinks = document.getElementById('nav-links');
    const overlay = document.getElementById('nav-overlay');

    if (!hamburger || !navLinks) return;

    function openNav() {
        navLinks.classList.add('open');
        overlay?.classList.add('visible');
        hamburger.innerHTML = '<i class="fas fa-times"></i>';
        document.body.style.overflow = 'hidden';
    }

    function closeNav() {
        navLinks.classList.remove('open');
        overlay?.classList.remove('visible');
        hamburger.innerHTML = '<i class="fas fa-bars"></i>';
        document.body.style.overflow = '';
    }

    function toggleNav() {
        if (navLinks.classList.contains('open')) {
            closeNav();
        } else {
            openNav();
        }
    }

    hamburger.addEventListener('click', toggleNav);
    overlay?.addEventListener('click', closeNav);

    // Close on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && navLinks.classList.contains('open')) {
            closeNav();
        }
    });

    // Close nav when clicking a link
    navLinks.querySelectorAll('.nav-link').forEach(function(link) {
        link.addEventListener('click', closeNav);
    });
}

/**
 * Custom modal dialogs, replaces browser confirm() and alert() so popups
 * inherit the app's font and style instead of looking like system dialogs.
 *
 * Usage:
 *   await LibertasModal.confirm('Delete this item?')           → true/false
 *   await LibertasModal.confirm('Delete?', { danger: true })   → true/false (red button)
 *   await LibertasModal.alert('Something went wrong.')         → void
 */
const LibertasModal = {
    /**
     * Show a confirmation dialog. Returns a Promise<boolean>.
     * @param {string} message
     * @param {Object} [opts]
     * @param {boolean} [opts.danger] - Style confirm button red (destructive actions)
     * @param {string}  [opts.confirmText] - Label for confirm button (default "OK")
     * @param {string}  [opts.cancelText]  - Label for cancel button (default "Cancel")
     */
    confirm: function(message, opts) {
        opts = opts || {};
        return new Promise(function(resolve) {
            var overlay = LibertasModal._buildOverlay();
            var modal   = LibertasModal._buildModal(message, [
                { label: opts.cancelText  || 'Cancel', cls: 'app-modal-btn-cancel',
                  action: function() { LibertasModal._dismiss(overlay); resolve(false); } },
                { label: opts.confirmText || 'OK',     cls: 'app-modal-btn-confirm' + (opts.danger ? ' danger' : ''),
                  action: function() { LibertasModal._dismiss(overlay); resolve(true);  } }
            ]);
            overlay.appendChild(modal);
            document.body.appendChild(overlay);
            // Focus the cancel button by default (safer for destructive actions)
            modal.querySelector('.app-modal-btn-cancel').focus();
        });
    },

    /**
     * Show an informational alert. Returns a Promise<void>.
     * @param {string} message
     */
    alert: function(message) {
        return new Promise(function(resolve) {
            var overlay = LibertasModal._buildOverlay();
            var modal   = LibertasModal._buildModal(message, [
                { label: 'OK', cls: 'app-modal-btn-confirm',
                  action: function() { LibertasModal._dismiss(overlay); resolve(); } }
            ]);
            overlay.appendChild(modal);
            document.body.appendChild(overlay);
            modal.querySelector('.app-modal-btn-confirm').focus();
        });
    },

    _buildOverlay: function() {
        var overlay = document.createElement('div');
        overlay.className = 'app-modal-overlay';
        return overlay;
    },

    _buildModal: function(message, buttons) {
        var modal = document.createElement('div');
        modal.className = 'app-modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');

        // Escape HTML in message, but support a leading bold line separated by \n\n
        var parts = message.split('\n\n');
        var bodyHtml = '';
        if (parts.length > 1) {
            bodyHtml = '<p class="app-modal-title">' + _escapeModalText(parts[0]) + '</p>' +
                       '<p class="app-modal-message">' + _escapeModalText(parts.slice(1).join('\n\n')) + '</p>';
        } else {
            bodyHtml = '<p class="app-modal-message">' + _escapeModalText(message) + '</p>';
        }

        var actionsHtml = buttons.map(function(b) {
            return '<button class="app-modal-btn ' + b.cls + '">' + _escapeModalText(b.label) + '</button>';
        }).join('');

        modal.innerHTML = bodyHtml + '<div class="app-modal-actions">' + actionsHtml + '</div>';

        // Bind button actions
        var btns = modal.querySelectorAll('.app-modal-btn');
        buttons.forEach(function(b, i) { btns[i].addEventListener('click', b.action); });

        return modal;
    },

    _dismiss: function(overlay) {
        if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }
};

function _escapeModalText(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Close modal on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        var overlay = document.querySelector('.app-modal-overlay');
        if (overlay) {
            // Treat Escape as Cancel (resolve false / dismiss)
            var cancelBtn = overlay.querySelector('.app-modal-btn-cancel');
            if (cancelBtn) cancelBtn.click();
            else {
                var okBtn = overlay.querySelector('.app-modal-btn-confirm');
                if (okBtn) okBtn.click();
            }
        }
    }
});

/**
 * Shared utility functions, single source of truth.
 * Used by create.js, trip.js, trips.js, calendar.js, item-detail.js, etc.
 * Do NOT redefine these in other files.
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatTime12Hour(time24) {
    if (!time24) return '';
    const [hours, minutes] = time24.split(':');
    const hour = parseInt(hours, 10);
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const hour12 = hour % 12 || 12;
    return `${hour12}:${minutes} ${ampm}`;
}

/**
 * Minimal markdown to HTML: bold, italic, headers, paragraphs.
 */
function mdToHtml(text) {
    let html = escapeHtml(text);
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    // Links: [text](url)
    html = html.replace(/\[(.+?)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');
    return '<p>' + html + '</p>';
}

/**
 * Initialize a Leaflet map with circle markers from a markers array.
 * Used by /r/ and /w/ recommendation pages.
 * @param {string} containerId - DOM element ID for the map
 * @param {Array} markers - [{lat, lng, title, category}, ...]
 */
function initRecommendationMap(containerId, markers) {
    if (!markers || markers.length === 0) {
        const el = document.getElementById(containerId);
        if (el) el.style.display = 'none';
        return null;
    }
    const map = L.map(containerId);
    L.tileLayer(LibertasMap.tileUrl, LibertasMap.tileOptions).addTo(map);

    const colors = {
        meal: '#FF9800', activity: '#34A853', attraction: '#34A853',
        hotel: '#4285F4', other: '#667eea'
    };
    const bounds = [];
    markers.forEach(m => {
        const color = colors[m.category] || '#667eea';
        L.circleMarker([m.lat, m.lng], {
            radius: 8, fillColor: color, color: '#fff', weight: 2, fillOpacity: 0.9
        }).addTo(map).bindPopup(m.title);
        bounds.push([m.lat, m.lng]);
    });
    if (bounds.length === 1) map.setView(bounds[0], 13);
    else map.fitBounds(bounds, { padding: [30, 30] });
    return map;
}

/**
 * Show a styled "Save to my trips" modal. Used by /r/ and /w/ pages.
 * @param {string} sourceLink - trip link to clone from
 * @param {string} title - trip title for creating new trips
 * @param {HTMLElement} btn - button to update on success
 */
async function showSaveToTripModal(sourceLink, title, btn) {
    const listRes = await fetch('/api/trips/list');
    if (listRes.status === 401) {
        window.location.href = '/register?redirect=' + encodeURIComponent(window.location.pathname);
        return;
    }
    const trips = (await listRes.json()).trips || [];

    async function doClone(targetLink) {
        const res = await fetch('/api/trips/clone-ideas', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({source_link: sourceLink, target_link: targetLink})
        });
        const data = await res.json();
        if (data.success) {
            btn.innerHTML = '<i class="fas fa-check"></i> Saved!';
            btn.classList.add('saved');
            btn.disabled = true;
        }
    }

    async function createAndClone() {
        const res = await fetch('/api/trips/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title: title})
        });
        const data = await res.json();
        const link = data.trip?.link || data.link;
        if (link) await doClone(link);
    }

    if (trips.length === 0) {
        await createAndClone();
        return;
    }

    // Show styled modal
    const old = document.getElementById('save-modal');
    if (old) old.remove();
    const overlay = document.createElement('div');
    overlay.id = 'save-modal';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:10000';
    overlay.innerHTML =
        '<div style="background:white;border-radius:14px;width:90%;max-width:400px;max-height:70vh;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,0.2)">' +
        '<div style="display:flex;align-items:center;justify-content:space-between;padding:20px 24px 16px;border-bottom:1px solid #eee">' +
        '<h3 style="margin:0;font-size:1.1rem;color:#333">Save to trip</h3>' +
        '<button id="save-modal-close" style="background:none;border:none;font-size:1.1rem;color:#999;cursor:pointer;padding:4px 8px"><i class="fas fa-times"></i></button></div>' +
        '<div style="overflow-y:auto;max-height:50vh;padding:8px">' +
        '<button class="save-pick" data-action="new" style="display:flex;align-items:center;gap:12px;width:100%;padding:14px 16px;border:none;background:none;border-radius:10px;font-size:0.95rem;color:#667eea;cursor:pointer;text-align:left;font-weight:600;border-bottom:1px solid #eee"><i class="fas fa-plus-circle"></i> New trip</button>' +
        trips.map(t =>
            '<button class="save-pick" data-link="' + t.link + '" style="display:flex;align-items:center;gap:12px;width:100%;padding:14px 16px;border:none;background:none;border-radius:10px;font-size:0.95rem;color:#333;cursor:pointer;text-align:left"><i class="fas fa-suitcase" style="color:#667eea"></i> ' + escapeHtml(t.title) + '</button>'
        ).join('') +
        '</div></div>';

    overlay.addEventListener('click', async (e) => {
        if (e.target === overlay || e.target.closest('#save-modal-close')) { overlay.remove(); return; }
        const item = e.target.closest('.save-pick');
        if (!item) return;
        overlay.remove();
        if (item.dataset.action === 'new') await createAndClone();
        else await doClone(item.dataset.link);
    });
    document.addEventListener('keydown', function esc(e) {
        if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', esc); }
    });
    document.body.appendChild(overlay);
}

/**
 * Initialize the page when DOM is ready
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize mobile navigation
    initMobileNav();

    console.log('Libertas loaded');
});

/**
 * Feedback / invite-request popup. Replaces the mailto: link in the footer
 * (and similar), most users don't have a mail client configured, so a
 * mailto link silently fails. This pops a small modal with:
 *   - The email shown visibly so anyone can copy it manually
 *   - A one-click Copy button (uses navigator.clipboard with fallback)
 *   - Quick-open links for Gmail and Outlook web compose
 *   - A mailto: link for users with a default mail app
 */
window.showFeedbackPopup = function (subject) {
    const email = 'aabtzu@gmail.com';
    const subj = subject || 'Libertas feedback';
    const subjEnc = encodeURIComponent(subj);

    // Build modal
    const overlay = document.createElement('div');
    overlay.className = 'feedback-popup-overlay';
    overlay.innerHTML = `
        <div class="feedback-popup">
            <button class="feedback-popup-close" aria-label="Close">&times;</button>
            <h3>Send feedback</h3>
            <p class="feedback-popup-body">Reach Amit at:</p>
            <div class="feedback-popup-email">
                <code>${email}</code>
                <button class="feedback-popup-copy" type="button">
                    <i class="fas fa-copy"></i> Copy
                </button>
            </div>
            <p class="feedback-popup-hint">Or open compose in:</p>
            <div class="feedback-popup-links">
                <a class="feedback-popup-btn"
                   href="https://mail.google.com/mail/?view=cm&fs=1&to=${email}&su=${subjEnc}"
                   target="_blank" rel="noopener">
                   <i class="fab fa-google"></i> Gmail
                </a>
                <a class="feedback-popup-btn"
                   href="https://outlook.live.com/mail/0/deeplink/compose?to=${email}&subject=${subjEnc}"
                   target="_blank" rel="noopener">
                   <i class="fas fa-envelope"></i> Outlook
                </a>
                <a class="feedback-popup-btn feedback-popup-btn-secondary"
                   href="mailto:${email}?subject=${subjEnc}">
                   <i class="fas fa-paper-plane"></i> Default mail app
                </a>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    // Wire close handlers
    const close = () => overlay.remove();
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay || e.target.closest('.feedback-popup-close')) {
            close();
        }
    });
    const onEsc = (e) => {
        if (e.key === 'Escape') {
            close();
            document.removeEventListener('keydown', onEsc);
        }
    };
    document.addEventListener('keydown', onEsc);

    // Wire copy button
    const copyBtn = overlay.querySelector('.feedback-popup-copy');
    copyBtn.addEventListener('click', async () => {
        let copied = false;
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(email);
                copied = true;
            }
        } catch { /* fall through */ }
        if (!copied) {
            // Fallback: select an off-screen textarea
            const ta = document.createElement('textarea');
            ta.value = email;
            ta.style.cssText = 'position:fixed;opacity:0;';
            document.body.appendChild(ta);
            ta.select();
            try { document.execCommand('copy'); copied = true; } catch {}
            document.body.removeChild(ta);
        }
        if (copied) {
            copyBtn.innerHTML = '<i class="fas fa-check"></i> Copied!';
            setTimeout(() => {
                copyBtn.innerHTML = '<i class="fas fa-copy"></i> Copy';
            }, 1800);
        }
    });
};
