/* Trip Page JavaScript - Libertas */
/* This file can be edited directly - no need to regenerate HTML */

// Export trip as JSON
function exportTrip() {
    var tripLink = window.location.pathname.split('/').pop();
    // The export endpoint returns a file download
    window.location.href = '/api/trips/' + encodeURIComponent(tripLink) + '/export';
}

// Regenerate map with fresh geocoding
function regenerateMap() {
    var tripLink = window.location.pathname.split('/').pop();

    // Show loading state
    var mapLoading = document.getElementById('map-loading');
    if (mapLoading) {
        mapLoading.classList.remove('hidden');
        mapLoading.innerHTML = '<div class="map-loading-spinner"></div>' +
            '<div class="map-loading-text">Regenerating map...</div>' +
            '<div class="map-loading-subtext">This may take a minute</div>';
    }

    fetch('/api/retry-geocoding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ link: tripLink })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            // Poll for completion then reload
            var badge = document.getElementById('map-status-badge');
            if (badge) badge.innerHTML = '<i class="fas fa-spinner fa-spin" style="color:#667eea;margin-left:5px;"></i>';
        } else {
            alert('Failed to regenerate map: ' + (data.error || 'Unknown error'));
            if (mapLoading) mapLoading.classList.add('hidden');
        }
    })
    .catch(function(err) {
        alert('Failed to regenerate map: ' + err);
        if (mapLoading) mapLoading.classList.add('hidden');
    });
}

// Tab switching
function switchTab(tabName) {
    // Remove active class from all tabs and content
    document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
    document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.remove('active'); });

    // Add active class to selected tab and content
    document.querySelector('.tab[onclick*="' + tabName + '"]').classList.add('active');
    document.getElementById(tabName + '-tab').classList.add('active');
}

// Initialize Leaflet Map
var map = null;
var markers = [];

function initMap() {
    var mapLoading = document.getElementById('map-loading');
    var mapContainer = document.getElementById('leaflet-map');

    if (!mapData || mapData.error) {
        if (mapLoading) {
            mapLoading.innerHTML = '<div class="map-status-error"><i class="fas fa-exclamation-triangle"></i></div>' +
                '<div class="map-loading-text map-status-error">Map not available</div>' +
                '<div class="map-loading-subtext">' + (mapData.error || 'No location data') + '</div>';
        }
        return;
    }

    // Create Leaflet map
    map = L.map('leaflet-map').setView([mapData.center.lat, mapData.center.lng], mapData.zoom);

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Category icon mapping
    var categoryIcons = {
        'flight': 'fa-plane',
        'hotel': 'fa-bed',
        'lodging': 'fa-bed',
        'meal': 'fa-utensils',
        'restaurant': 'fa-utensils',
        'activity': 'fa-star',
        'attraction': 'fa-landmark',
        'transport': 'fa-car',
        'other': 'fa-map-marker-alt'
    };

    // Add markers with category icons
    mapData.markers.forEach(function(markerData, index) {
        var iconClass = categoryIcons[markerData.category] || 'fa-map-marker-alt';

        // Create custom div icon for Leaflet
        var icon = L.divIcon({
            className: 'custom-marker',
            html: '<div style="width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); background-color: ' + markerData.color + ';"><i class="fas ' + iconClass + '" style="color: white; font-size: 12px;"></i></div>',
            iconSize: [28, 28],
            iconAnchor: [14, 14],
            popupAnchor: [0, -14]
        });

        var marker = L.marker([markerData.position.lat, markerData.position.lng], { icon: icon })
            .addTo(map)
            .bindPopup(markerData.info, { maxWidth: 350 });

        markers.push(marker);
    });

    // Hide loading overlay
    if (mapLoading) mapLoading.classList.add('hidden');

    // Fix Leaflet size calculation for hidden containers
    setTimeout(function() {
        map.invalidateSize();
    }, 100);
}

// Initialize map when map tab becomes visible
(function() {
    var mapInitialized = false;

    function tryInitMap() {
        if (mapInitialized) return;
        if (mapData && mapData.markers && mapData.markers.length > 0 && !mapData.error) {
            mapInitialized = true;
            initMap();
        } else if (mapData && mapData.error) {
            // Show error message
            var mapLoading = document.getElementById('map-loading');
            if (mapLoading) {
                mapLoading.innerHTML = '<div class="map-status-error"><i class="fas fa-exclamation-triangle"></i></div>' +
                    '<div class="map-loading-text map-status-error">Map not available</div>' +
                    '<div class="map-loading-subtext">' + mapData.error + '</div>';
            }
        }
    }

    // Override switchTab to init map when map tab is selected
    var _originalSwitchTab = switchTab;
    switchTab = function(tabName) {
        _originalSwitchTab(tabName);
        if (tabName === 'map') {
            setTimeout(tryInitMap, 50);
        }
    };

    // Also check on page load if map tab is active
    document.addEventListener('DOMContentLoaded', function() {
        var mapTabContent = document.getElementById('map-tab');
        if (mapTabContent && mapTabContent.classList.contains('active')) {
            setTimeout(tryInitMap, 100);
        }
    });
})();

// Item popup - using event delegation for calendar items (click) and column items (double-click)
// Uses shared item-detail.js for popup display

document.addEventListener('click', function(event) {
    // Handle "+N more" click in calendar
    var moreElement = event.target.closest('.calendar-item-more');
    if (moreElement && moreElement.hasAttribute('data-hidden-items')) {
        event.stopPropagation();
        showCalendarMorePopup(moreElement);
        return;
    }

    // Handle calendar item click
    var calendarItem = event.target.closest('.calendar-item');
    if (calendarItem && calendarItem.hasAttribute('data-title')) {
        event.stopPropagation();
        showItemDetailPopup(calendarItem, event);
    }
});

// Double-click on column items, night-stay, or activity items to show detail popup
document.addEventListener('dblclick', function(event) {
    // Grid view items
    var columnItem = event.target.closest('.column-item');
    if (columnItem && columnItem.hasAttribute('data-title')) {
        event.stopPropagation();
        showItemDetailPopup(columnItem, event);
        return;
    }
    // Grid view night stay
    var nightStay = event.target.closest('.night-stay');
    if (nightStay && nightStay.hasAttribute('data-title')) {
        event.stopPropagation();
        showItemDetailPopup(nightStay, event);
        return;
    }
    // List view items
    var activityItem = event.target.closest('.activity');
    if (activityItem && activityItem.hasAttribute('data-title')) {
        event.stopPropagation();
        showItemDetailPopup(activityItem, event);
    }
});

// Store hidden items data for click handling
var _hiddenItemsData = [];

function showCalendarMorePopup(element) {
    // Remove any existing popup
    hideItemDetailPopup();

    // Parse hidden items data
    try {
        _hiddenItemsData = JSON.parse(element.getAttribute('data-hidden-items'));
    } catch (e) {
        console.error('Failed to parse hidden items:', e);
        return;
    }

    // Category icon mapping
    var categoryIcons = {
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

    // Create overlay
    var overlay = document.createElement('div');
    overlay.className = 'item-detail-overlay';
    overlay.onclick = hideItemDetailPopup;
    document.body.appendChild(overlay);

    // Create popup
    var popup = document.createElement('div');
    popup.className = 'item-detail-popup calendar-more-popup';
    popup.id = 'item-detail-popup';

    var itemsHtml = '<div class="more-items-list">';
    _hiddenItemsData.forEach(function(item, index) {
        var iconClass = categoryIcons[item.category] || 'fa-calendar-day';
        var detailParts = [];
        if (item.time) detailParts.push(item.time);
        if (item.location) detailParts.push(item.location);
        var detail = detailParts.join(' • ');

        // Make items clickable to show detail
        itemsHtml += '<div class="more-item" data-hidden-index="' + index + '" style="cursor:pointer;">' +
            '<div class="more-item-icon ' + item.category + '"><i class="fas ' + iconClass + '"></i></div>' +
            '<div class="more-item-content">' +
                '<div class="more-item-title">' + _escapeHtmlTrip(item.title) + '</div>' +
                (detail ? '<div class="more-item-detail">' + _escapeHtmlTrip(detail) + '</div>' : '') +
                (item.website ? '<div class="more-item-link"><i class="fas fa-globe"></i></div>' : '') +
            '</div>' +
        '</div>';
    });
    itemsHtml += '</div>';

    popup.innerHTML =
        '<button class="popup-close" onclick="hideItemDetailPopup()">&times;</button>' +
        '<div class="popup-header">' +
            '<div class="popup-title">More Activities</div>' +
        '</div>' +
        itemsHtml;

    document.body.appendChild(popup);

    // Add click handlers for items in the list
    popup.querySelectorAll('.more-item[data-hidden-index]').forEach(function(itemEl) {
        itemEl.addEventListener('click', function(e) {
            var idx = parseInt(itemEl.getAttribute('data-hidden-index'));
            var itemData = _hiddenItemsData[idx];
            if (itemData) {
                showItemDetailFromData(itemData, itemEl);
            }
        });
    });

    // Position popup near the clicked element (account for scroll)
    var rect = element.getBoundingClientRect();
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

// Helper to escape HTML
function _escapeHtmlTrip(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Legacy function name for compatibility
function hideCalendarItemPopup() {
    hideItemDetailPopup();
}

// Map status polling - only poll if map is pending/processing
(function() {
    var tripLink = window.location.pathname.split('/').pop();
    var mapLoading = document.getElementById('map-loading');
    var mapBadge = document.getElementById('map-status-badge');
    var pollInterval = null;
    var wasNotReady = false;

    function checkMapStatus() {
        fetch('/api/map-status?link=' + encodeURIComponent(tripLink))
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.map_status === 'ready') {
                    if (mapBadge) mapBadge.innerHTML = '';
                    if (pollInterval) clearInterval(pollInterval);
                    if (wasNotReady) {
                        window.location.reload();
                    }
                } else if (data.map_status === 'error') {
                    if (mapLoading) {
                        mapLoading.innerHTML = '<div class="map-status-error"><i class="fas fa-exclamation-triangle"></i></div>' +
                            '<div class="map-loading-text map-status-error">Map generation failed</div>' +
                            '<div class="map-loading-subtext">' + (data.map_error || 'Unknown error') + '</div>';
                    }
                    if (mapBadge) mapBadge.innerHTML = '<i class="fas fa-exclamation-circle" style="color:#e74c3c;margin-left:5px;"></i>';
                    if (pollInterval) clearInterval(pollInterval);
                } else if (data.map_status === 'pending' || data.map_status === 'processing') {
                    wasNotReady = true;
                    if (mapLoading) mapLoading.classList.remove('hidden');
                    if (mapBadge) mapBadge.innerHTML = '<i class="fas fa-spinner fa-spin" style="color:#667eea;margin-left:5px;"></i>';
                }
            })
            .catch(function(err) {
                console.log('Map status check failed:', err);
            });
    }

    checkMapStatus();
    pollInterval = setInterval(checkMapStatus, 5000);
})();
