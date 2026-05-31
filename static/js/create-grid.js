// ==================== Grid / Calendar View ====================

/**
 * Switch between itinerary and map tabs
 */
function switchTimelineTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.timeline-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });

    // Update tab content
    document.querySelectorAll('.timeline-tab-content').forEach(content => {
        content.classList.toggle('active', content.id === tabName + '-tab');
    });

    // Initialize map when switching to map tab
    if (tabName === 'map') {
        updateMapDaySelector();
        initializeMap();
    }

    // Render grid when switching to grid tab
    if (tabName === 'grid') {
        renderGrid();
    }

    // Render calendar when switching to calendar tab
    if (tabName === 'calendar') {
        renderCalendar();
    }
}

/**
 * Render the grid view (column table like trip detail pages)
 * Columns: Day | Travel | Activity | Night Stay | Notes
 */
function renderGrid() {
    const container = document.getElementById('grid-container');
    if (!container) return;

    container.innerHTML = '';

    if (currentTrip.days.length === 0) {
        container.innerHTML = `
            <div class="grid-empty">
                <i class="fas fa-th-large" style="font-size: 3rem; color: #ddd; margin-bottom: 16px;"></i>
                <p>No days to display. Add dates or days to your trip first.</p>
            </div>
        `;
        return;
    }

    // Track night stay for carry-forward
    let lastNightStay = null;
    const lastDayNum = currentTrip.days[currentTrip.days.length - 1].day_number;

    // Pre-compute which day indices have lodging, so carry-forward knows when to stop
    const lodgingDayNums = new Set(
        currentTrip.days
            .filter(d => (d.items || []).some(i => ['hotel','lodging'].includes((i.category||'').toLowerCase())))
            .map(d => d.day_number)
    );

    // Build table HTML
    let tableHtml = `
        <div class="column-table-wrapper">
            <table class="column-table">
                <thead>
                    <tr>
                        <th>Day</th>
                        <th>Travel</th>
                        <th>Activity</th>
                        <th>Night Stay</th>
                        <th>Notes</th>
                    </tr>
                </thead>
                <tbody>
    `;

    currentTrip.days.forEach((day, index) => {
        // Categorize items
        const travelItems = [];
        const activityItems = [];
        const lodgingItems = [];
        const notesItems = [];
        let hasFlight = false;

        (day.items || []).forEach(item => {
            const cat = (item.category || 'other').toLowerCase();
            if (cat === 'flight') {
                travelItems.push(item);
                hasFlight = true;
            } else if (cat === 'transport' || cat === 'train' || cat === 'bus') {
                travelItems.push(item);
            } else if (cat === 'hotel' || cat === 'lodging') {
                lodgingItems.push(item);
            } else if (cat === 'activity' || cat === 'attraction' || cat === 'meal') {
                activityItems.push(item);
            } else {
                notesItems.push(item);
            }
        });

        // Determine night stay
        let currentNightStay = null;
        let isCarried = false;
        if (lodgingItems.length > 0) {
            const lastLodging = lodgingItems[lodgingItems.length - 1];
            currentNightStay = lastLodging.title || lastLodging.location || null;
            lastNightStay = lastLodging;  // store full item so we can check end_date
        } else if (lastNightStay) {
            const isLastDay = (day.day_number === lastDayNum);
            let withinStay = false;
            if (lastNightStay.end_date && day.date) {
                // Has explicit checkout, carry while before that date
                withinStay = day.date < lastNightStay.end_date;
            } else {
                // No end_date, carry until the next day that has its own lodging
                const nextLodgingDay = currentTrip.days
                    .find(d => d.day_number > day.day_number && lodgingDayNums.has(d.day_number));
                withinStay = !nextLodgingDay || day.day_number < nextLodgingDay.day_number;
            }
            // Only stop carry on a flight day if it's also the trip's last day
            // (departure home). Mid-trip flights should not break the lodging chain.
            const isFlightDeparture = hasFlight && isLastDay;
            if (!isLastDay && !isFlightDeparture && withinStay) {
                currentNightStay = lastNightStay.title || lastNightStay.location || null;
                isCarried = true;
            } else {
                lastNightStay = null;  // stop carrying, checkout reached or next lodging found
            }
        }

        // Format date
        const dateStr = day.date ? formatDate(day.date) : '';
        const dayLabel = `Day ${day.day_number}${dateStr ? '<br><small>' + dateStr + '</small>' : ''}`;

        tableHtml += '<tr>';

        // Day column
        tableHtml += `<td style="font-weight:600;white-space:nowrap;">${dayLabel}</td>`;

        // Travel column
        tableHtml += '<td>' + formatColumnItems(travelItems) + '</td>';

        // Activity column
        tableHtml += '<td>' + formatColumnItems(activityItems) + '</td>';

        // Night Stay column
        if (currentNightStay) {
            const carriedClass = isCarried ? ' carried' : '';
            tableHtml += `<td><div class="night-stay${carriedClass}"><i class="fas fa-bed"></i>${escapeHtml(currentNightStay)}</div></td>`;
        } else {
            tableHtml += '<td><span class="column-empty">-</span></td>';
        }

        // Notes column
        tableHtml += '<td>' + formatColumnItems(notesItems, true) + '</td>';

        tableHtml += '</tr>';
    });

    tableHtml += '</tbody></table></div>';
    container.innerHTML = tableHtml;
}

/**
 * Render the calendar view using shared CalendarView module
 */
function renderCalendar() {
    const container = document.getElementById('calendar-container');
    if (!container) return;

    // Use the shared CalendarView module to render
    container.innerHTML = CalendarView.render(currentTrip, { editable: true });

    // Set up click handlers for calendar items
    setupCalendarClickHandlers(container);
}

/**
 * Set up click handlers for calendar items in the edit view
 */
function setupCalendarClickHandlers(container) {
    // Handle calendar item clicks - show edit dialog
    container.addEventListener('click', function(event) {
        // Handle "+N more" click
        const moreElement = event.target.closest('.calendar-item-more');
        if (moreElement && moreElement.hasAttribute('data-hidden-items')) {
            event.stopPropagation();
            showCalendarMorePopup(moreElement);
            return;
        }

        // Handle calendar item click - open edit modal
        const calendarItem = event.target.closest('.calendar-item');
        if (calendarItem) {
            event.stopPropagation();
            const dayIndex = parseInt(calendarItem.dataset.dayIndex);
            const itemIndex = parseInt(calendarItem.dataset.itemIndex);
            if (!isNaN(dayIndex) && !isNaN(itemIndex)) {
                editItem(dayIndex, itemIndex);
            }
        }
    });
}

/**
 * Show popup with hidden calendar items
 */
function showCalendarMorePopup(element) {
    try {
        const hiddenItems = JSON.parse(element.dataset.hiddenItems);
        // Use existing item detail popup logic
        if (typeof showItemDetailPopup === 'function') {
            // Create a temporary container with the items
            let popupHtml = '<div class="more-items-list">';
            hiddenItems.forEach((item, index) => {
                const iconClass = CalendarView.getCategoryIcon(item.category);
                const detailParts = [];
                if (item.time) detailParts.push(item.time);
                if (item.location) detailParts.push(item.location);

                popupHtml += `
                    <div class="more-item" data-index="${index}">
                        <div class="more-item-header">
                            <i class="fas ${iconClass}"></i>
                            <span class="more-item-title">${escapeHtml(item.title)}</span>
                        </div>
                        ${detailParts.length ? `<div class="more-item-detail">${escapeHtml(detailParts.join(' • '))}</div>` : ''}
                    </div>
                `;
            });
            popupHtml += '</div>';

            // Show as a simple popup near the element
            const popup = document.createElement('div');
            popup.className = 'item-detail-popup calendar-more-popup';
            popup.innerHTML = popupHtml;

            const overlay = document.createElement('div');
            overlay.className = 'item-detail-overlay';
            overlay.onclick = () => { overlay.remove(); popup.remove(); };

            document.body.appendChild(overlay);
            document.body.appendChild(popup);

            // Position the popup
            const rect = element.getBoundingClientRect();
            popup.style.left = Math.min(rect.left, window.innerWidth - 340) + 'px';
            popup.style.top = Math.min(rect.bottom + 5, window.innerHeight - popup.offsetHeight - 10) + 'px';
        }
    } catch (e) {
        console.error('Error showing calendar more popup:', e);
    }
}

/**
 * Format items for a column cell (shared formatting with list view)
 */
function formatColumnItems(items, isNotes = false) {
    if (items.length === 0) {
        return '<span class="column-empty">-</span>';
    }

    return items.map(item => renderItemCard(item, { showNotes: isNotes, compact: true })).join('');
}

/**
 * Shared item card renderer - used by both list and grid views
 */
function renderItemCard(item, options = {}) {
    const { showNotes = false, compact = false, dayIndex = null, itemIndex = null, draggable = false } = options;
    const cat = (item.category || 'other').toLowerCase();
    const iconClass = getItemIcon(item);
    let timeStr = '';
    if (item.time) {
        timeStr = formatTime12Hour(item.time);
        if (item.end_time) {
            const isTravel = (cat === 'travel' || cat === 'flight' || cat === 'transport' || cat === 'train' || cat === 'bus');
            const separator = isTravel ? ' → ' : ' - ';
            timeStr += separator + formatTime12Hour(item.end_time);
        }
    }
    const locationStr = item.location || '';

    if (compact) {
        // Compact mode for grid view
        let html = `<div class="column-item ${cat}">`;
        html += `<div class="column-item-title"><i class="fas ${iconClass} column-item-icon"></i> ${escapeHtml(item.title)}</div>`;
        if (timeStr) {
            html += `<div class="column-item-time"><i class="fas fa-clock"></i> ${timeStr}</div>`;
        }
        if (locationStr && !showNotes) {
            html += `<div class="column-item-location"><i class="fas fa-map-marker-alt"></i> ${escapeHtml(locationStr)}</div>`;
        }
        if (item.notes && showNotes) {
            html += `<div class="column-item-notes">${escapeHtml(item.notes)}</div>`;
        }
        html += '</div>';
        return html;
    }

    // Full mode for list view
    const draggableAttr = draggable ? 'draggable="true"' : '';
    const dataAttrs = dayIndex !== null ? `data-day-index="${dayIndex}" data-item-index="${itemIndex}"` : '';

    return `
        <div class="item-card ${cat}" ${dataAttrs} ${draggableAttr}>
            <div class="item-icon ${cat}">
                <i class="fas ${iconClass}"></i>
            </div>
            <div class="item-content">
                <div class="item-title">${escapeHtml(item.title)}</div>
                <div class="item-meta">
                    ${timeStr ? `<span><i class="fas fa-clock"></i> ${timeStr}</span>` : ''}
                    ${locationStr ? `<span><i class="fas fa-map-marker-alt"></i> ${locationStr}</span>` : ''}
                </div>
            </div>
            ${dayIndex !== null ? `
            <div class="item-actions">
                <button onclick="editItem(${dayIndex}, ${itemIndex})" title="Edit">
                    <i class="fas fa-edit"></i>
                </button>
                <button onclick="deleteItem(${dayIndex}, ${itemIndex})" title="Delete">
                    <i class="fas fa-trash"></i>
                </button>
            </div>` : ''}
        </div>
    `;
}

/**
 * Get day of week from date string
 */
function getDayOfWeek(dateStr) {
    const date = new Date(dateStr + 'T12:00:00');
    return date.toLocaleDateString('en-US', { weekday: 'long' });
}

// formatDate and escapeHtml are defined in create.js

/**
 * Update the day selector dropdown for map view
 */
