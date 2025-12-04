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
 * Initialize the page when DOM is ready
 */
document.addEventListener('DOMContentLoaded', function() {
    // Add any initialization code here
    console.log('Libertas loaded');
});
