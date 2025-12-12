/* Libertas - Main JavaScript */

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
 * Initialize the page when DOM is ready
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize mobile navigation
    initMobileNav();

    console.log('Libertas loaded');
});
