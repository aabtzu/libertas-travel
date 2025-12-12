/* Libertas - Main JavaScript */

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
