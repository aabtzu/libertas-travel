/* Libertas - Main JavaScript */

/**
 * Shared category→icon and category→color maps.
 * Single source of truth — used by create.js, create-grid.js, create-map.js,
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
 * Shared file upload validation — single source of truth for allowed types.
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
 * Custom modal dialogs — replaces browser confirm() and alert() so popups
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
 * Shared utility functions — single source of truth.
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
 * Initialize the page when DOM is ready
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize mobile navigation
    initMobileNav();

    console.log('Libertas loaded');
});
