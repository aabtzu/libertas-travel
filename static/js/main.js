/* Libertas - Main JavaScript */

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
