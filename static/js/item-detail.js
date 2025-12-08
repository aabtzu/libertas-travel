/* Shared Item Detail Popup - Libertas */
/* Used by both trip view and create trip pages */

// Category icon mapping
var itemDetailIcons = {
    'flight': 'fa-plane',
    'hotel': 'fa-bed',
    'lodging': 'fa-bed',
    'meal': 'fa-utensils',
    'restaurant': 'fa-utensils',
    'activity': 'fa-star',
    'attraction': 'fa-landmark',
    'transport': 'fa-car',
    'other': 'fa-calendar-day'
};

/**
 * Show item detail popup for a data-attribute based element
 * @param {HTMLElement} element - Element with data-* attributes
 * @param {Event} event - Optional click event for positioning
 */
function showItemDetailPopup(element, event) {
    // Remove any existing popup
    hideItemDetailPopup();

    // Get data from element
    var data = {
        title: element.getAttribute('data-title') || 'Activity',
        time: element.getAttribute('data-time') || '',
        location: element.getAttribute('data-location') || '',
        category: element.getAttribute('data-category') || 'other',
        website: element.getAttribute('data-website') || '',
        notes: element.getAttribute('data-notes') || ''
    };

    _createAndShowPopup(data, element);
}

/**
 * Show item detail popup from a data object (for hidden items in "+N more")
 * @param {Object} data - Item data object with title, time, location, category, website, notes
 * @param {HTMLElement} anchorElement - Element to position popup near
 */
function showItemDetailFromData(data, anchorElement) {
    hideItemDetailPopup();
    _createAndShowPopup(data, anchorElement);
}

/**
 * Internal function to create and display the popup
 */
function _createAndShowPopup(data, anchorElement) {
    var iconClass = itemDetailIcons[data.category] || 'fa-calendar-day';

    // Create overlay
    var overlay = document.createElement('div');
    overlay.className = 'item-detail-overlay';
    overlay.onclick = hideItemDetailPopup;
    document.body.appendChild(overlay);

    // Create popup
    var popup = document.createElement('div');
    popup.className = 'item-detail-popup';
    popup.id = 'item-detail-popup';

    // Build details HTML
    var detailsHtml = '';
    if (data.time) {
        detailsHtml += '<div class="popup-detail"><i class="fas fa-clock"></i><span>' + _escapeHtml(data.time) + '</span></div>';
    }
    if (data.location) {
        detailsHtml += '<div class="popup-detail"><i class="fas fa-map-marker-alt"></i><span>' + _escapeHtml(data.location) + '</span></div>';
    }
    if (data.website) {
        detailsHtml += '<div class="popup-detail"><i class="fas fa-globe"></i><a href="' + _escapeHtml(data.website) + '" target="_blank" rel="noopener">' + _shortenUrl(data.website) + '</a></div>';
    }
    if (data.notes) {
        detailsHtml += '<div class="popup-detail popup-notes"><i class="fas fa-sticky-note"></i><span>' + _escapeHtml(data.notes) + '</span></div>';
    }

    popup.innerHTML =
        '<button class="popup-close" onclick="hideItemDetailPopup()">&times;</button>' +
        '<div class="popup-header">' +
            '<div class="popup-icon ' + data.category + '"><i class="fas ' + iconClass + '"></i></div>' +
            '<div class="popup-title">' + _escapeHtml(data.title) + '</div>' +
        '</div>' +
        (detailsHtml ? '<div class="popup-details">' + detailsHtml + '</div>' : '');

    document.body.appendChild(popup);

    // Position popup near the anchor element
    _positionPopup(popup, anchorElement);
}

/**
 * Position popup relative to anchor element
 */
function _positionPopup(popup, anchorElement) {
    var rect = anchorElement.getBoundingClientRect();
    var popupRect = popup.getBoundingClientRect();
    var scrollX = window.pageXOffset || document.documentElement.scrollLeft;
    var scrollY = window.pageYOffset || document.documentElement.scrollTop;

    var left = rect.left + scrollX + rect.width / 2 - popupRect.width / 2;
    var top = rect.bottom + scrollY + 8;

    // Keep within viewport
    if (left < scrollX + 10) left = scrollX + 10;
    if (left + popupRect.width > scrollX + window.innerWidth - 10) {
        left = scrollX + window.innerWidth - popupRect.width - 10;
    }
    if (top + popupRect.height > scrollY + window.innerHeight - 10) {
        top = rect.top + scrollY - popupRect.height - 8;
    }

    popup.style.left = left + 'px';
    popup.style.top = top + 'px';
}

/**
 * Hide the item detail popup
 */
function hideItemDetailPopup() {
    var popup = document.getElementById('item-detail-popup');
    if (popup) popup.remove();
    var overlay = document.querySelector('.item-detail-overlay');
    if (overlay) overlay.remove();
}

/**
 * Escape HTML to prevent XSS
 */
function _escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Shorten URL for display
 */
function _shortenUrl(url) {
    try {
        var u = new URL(url);
        var display = u.hostname.replace('www.', '');
        if (u.pathname && u.pathname !== '/') {
            display += u.pathname.substring(0, 20);
            if (u.pathname.length > 20) display += '...';
        }
        return display;
    } catch (e) {
        return url.substring(0, 30) + (url.length > 30 ? '...' : '');
    }
}

// Close popup on escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') hideItemDetailPopup();
});
