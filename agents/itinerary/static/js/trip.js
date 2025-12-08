/* Trip Page JavaScript - Libertas */
/* This file can be edited directly - no need to regenerate HTML */

// Export trip as JSON
function exportTrip() {
    var tripLink = window.location.pathname.split('/').pop();
    // The export endpoint returns a file download
    window.location.href = '/api/trips/' + encodeURIComponent(tripLink) + '/export';
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

// Initialize Google Map
var map = null;
var markers = [];
var infoWindow = null;

function initMap() {
    var mapLoading = document.getElementById('map-loading');

    if (!mapData || mapData.error) {
        if (mapLoading) {
            mapLoading.innerHTML = '<div class="map-status-error"><i class="fas fa-exclamation-triangle"></i></div>' +
                '<div class="map-loading-text map-status-error">Map not available</div>' +
                '<div class="map-loading-subtext">' + (mapData.error || 'No location data') + '</div>';
        }
        return;
    }

    // Create map with mapId for AdvancedMarkerElement support
    map = new google.maps.Map(document.getElementById('google-map'), {
        center: mapData.center,
        zoom: mapData.zoom,
        mapId: 'DEMO_MAP_ID',
        mapTypeControl: true,
        mapTypeControlOptions: {
            style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
            position: google.maps.ControlPosition.TOP_RIGHT
        },
        fullscreenControl: true,
        streetViewControl: false,
    });

    // Create info window
    infoWindow = new google.maps.InfoWindow();

    // Category icon mapping (using Font Awesome class names)
    var categoryIcons = {
        'flight': 'fa-plane',
        'hotel': 'fa-bed',
        'lodging': 'fa-bed',
        'meal': 'fa-utensils',
        'restaurant': 'fa-utensils',
        'activity': 'fa-star',
        'attraction': 'fa-star',
        'transport': 'fa-car',
        'other': 'fa-map-marker-alt'
    };

    // Add markers with category icons using custom HTML
    mapData.markers.forEach(function(markerData, index) {
        var iconClass = categoryIcons[markerData.category] || 'fa-map-marker-alt';

        // Create custom marker element
        var markerDiv = document.createElement('div');
        markerDiv.style.cssText = 'width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); cursor: pointer; background-color: ' + markerData.color + ';';
        markerDiv.innerHTML = '<i class="fas ' + iconClass + '" style="color: white; font-size: 12px;"></i>';

        var marker = new google.maps.marker.AdvancedMarkerElement({
            position: markerData.position,
            map: map,
            title: markerData.title,
            content: markerDiv
        });

        marker.addListener('click', function() {
            infoWindow.setContent(markerData.info);
            infoWindow.open(map, marker);
        });

        markers.push(marker);
    });

    // Hide loading overlay
    if (mapLoading) mapLoading.classList.add('hidden');
}

// Calendar item popup - using event delegation
document.addEventListener('click', function(event) {
    // Handle "+N more" click
    var moreElement = event.target.closest('.calendar-item-more');
    if (moreElement && moreElement.hasAttribute('data-hidden-items')) {
        event.stopPropagation();
        showCalendarMorePopup(moreElement);
        return;
    }

    var element = event.target.closest('.calendar-item');
    if (element && element.hasAttribute('data-title')) {
        event.stopPropagation();
        showCalendarItemPopup(element, event);
    }
});

function showCalendarItemPopup(element, event) {
    // Remove any existing popup
    hideCalendarItemPopup();

    // Get data from element
    var title = element.getAttribute('data-title') || 'Activity';
    var time = element.getAttribute('data-time') || '';
    var location = element.getAttribute('data-location') || '';
    var category = element.getAttribute('data-category') || 'other';

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
    var iconClass = categoryIcons[category] || 'fa-calendar-day';

    // Create overlay
    var overlay = document.createElement('div');
    overlay.className = 'calendar-popup-overlay';
    overlay.onclick = hideCalendarItemPopup;
    document.body.appendChild(overlay);

    // Create popup
    var popup = document.createElement('div');
    popup.className = 'calendar-item-popup';
    popup.id = 'calendar-popup';

    var detailsHtml = '';
    if (time) {
        detailsHtml += '<div class="popup-detail"><i class="fas fa-clock"></i><span>' + time + '</span></div>';
    }
    if (location) {
        detailsHtml += '<div class="popup-detail"><i class="fas fa-map-marker-alt"></i><span>' + location + '</span></div>';
    }

    popup.innerHTML =
        '<button class="popup-close" onclick="hideCalendarItemPopup()">&times;</button>' +
        '<div class="popup-header">' +
            '<div class="popup-icon ' + category + '"><i class="fas ' + iconClass + '"></i></div>' +
            '<div class="popup-title">' + title + '</div>' +
        '</div>' +
        (detailsHtml ? '<div class="popup-details">' + detailsHtml + '</div>' : '');

    document.body.appendChild(popup);

    // Position popup near the clicked element
    var rect = element.getBoundingClientRect();
    var popupRect = popup.getBoundingClientRect();

    var left = rect.left + rect.width / 2 - popupRect.width / 2;
    var top = rect.bottom + 8;

    // Keep within viewport
    if (left < 10) left = 10;
    if (left + popupRect.width > window.innerWidth - 10) {
        left = window.innerWidth - popupRect.width - 10;
    }
    if (top + popupRect.height > window.innerHeight - 10) {
        top = rect.top - popupRect.height - 8;
    }

    popup.style.left = left + 'px';
    popup.style.top = top + 'px';
}

function hideCalendarItemPopup() {
    var popup = document.getElementById('calendar-popup');
    if (popup) popup.remove();
    var overlay = document.querySelector('.calendar-popup-overlay');
    if (overlay) overlay.remove();
}

function showCalendarMorePopup(element) {
    // Remove any existing popup
    hideCalendarItemPopup();

    // Parse hidden items data
    var hiddenItems = [];
    try {
        hiddenItems = JSON.parse(element.getAttribute('data-hidden-items'));
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
    overlay.className = 'calendar-popup-overlay';
    overlay.onclick = hideCalendarItemPopup;
    document.body.appendChild(overlay);

    // Create popup
    var popup = document.createElement('div');
    popup.className = 'calendar-item-popup calendar-more-popup';
    popup.id = 'calendar-popup';

    var itemsHtml = '<div class="more-items-list">';
    hiddenItems.forEach(function(item) {
        var iconClass = categoryIcons[item.category] || 'fa-calendar-day';
        var detailParts = [];
        if (item.time) detailParts.push(item.time);
        if (item.location) detailParts.push(item.location);
        var detail = detailParts.join(' • ');

        itemsHtml += '<div class="more-item">' +
            '<div class="more-item-icon ' + item.category + '"><i class="fas ' + iconClass + '"></i></div>' +
            '<div class="more-item-content">' +
                '<div class="more-item-title">' + item.title + '</div>' +
                (detail ? '<div class="more-item-detail">' + detail + '</div>' : '') +
            '</div>' +
        '</div>';
    });
    itemsHtml += '</div>';

    popup.innerHTML =
        '<button class="popup-close" onclick="hideCalendarItemPopup()">&times;</button>' +
        '<div class="popup-header">' +
            '<div class="popup-title">More Activities</div>' +
        '</div>' +
        itemsHtml;

    document.body.appendChild(popup);

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

// Close popup on escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') hideCalendarItemPopup();
});

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
