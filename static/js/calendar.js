/**
 * Shared Calendar View Module
 * Used by both trip view (trip.js) and trip editor (create.js)
 */

const CalendarView = (function() {
    'use strict';

    const CATEGORY_ICONS = {
        'travel': 'fa-plane',
        'flight': 'fa-plane',
        'transport': 'fa-car',
        'train': 'fa-train',
        'bus': 'fa-bus',
        'hotel': 'fa-bed',
        'lodging': 'fa-bed',
        'meal': 'fa-utensils',
        'activity': 'fa-star',
        'attraction': 'fa-landmark',
        'other': 'fa-calendar-day'
    };

    /**
     * Escape HTML to prevent XSS
     */
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Get category icon class
     */
    function getCategoryIcon(category) {
        return CATEGORY_ICONS[(category || 'other').toLowerCase()] || 'fa-calendar-day';
    }

    /**
     * Format time to 12-hour format
     */
    function formatTime12Hour(timeStr) {
        if (!timeStr) return '';
        const [hours, minutes] = timeStr.split(':');
        const h = parseInt(hours);
        const period = h >= 12 ? 'PM' : 'AM';
        const hour12 = h === 0 ? 12 : (h > 12 ? h - 12 : h);
        return `${hour12}:${minutes} ${period}`;
    }

    /**
     * Parse a date string to Date object (handles YYYY-MM-DD)
     */
    function parseDate(dateStr) {
        if (!dateStr) return null;
        // Use noon to avoid timezone issues
        return new Date(dateStr + 'T12:00:00');
    }

    /**
     * Format date as YYYY-MM-DD
     */
    function formatDateKey(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    /**
     * Get month name
     */
    function getMonthName(month) {
        const names = ['January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December'];
        return names[month];
    }

    /**
     * Build calendar HTML for a single month
     */
    function buildMonthCalendar(year, month, tripStart, tripEnd, itemsByDate, options) {
        const monthName = getMonthName(month);
        const isEditable = options.editable || false;

        let html = `<div class="calendar-month">
            <h3 class="calendar-month-title">${monthName} ${year}</h3>
            <div class="calendar-grid">
                <div class="calendar-header">
                    <div class="calendar-day-name">Sun</div>
                    <div class="calendar-day-name">Mon</div>
                    <div class="calendar-day-name">Tue</div>
                    <div class="calendar-day-name">Wed</div>
                    <div class="calendar-day-name">Thu</div>
                    <div class="calendar-day-name">Fri</div>
                    <div class="calendar-day-name">Sat</div>
                </div>
                <div class="calendar-body">`;

        // Get calendar weeks for this month (starting Sunday)
        const weeks = getMonthWeeks(year, month);

        for (const week of weeks) {
            html += '<div class="calendar-week">';

            for (const dayDate of week) {
                const isTripDay = dayDate >= tripStart && dayDate <= tripEnd;
                const isCurrentMonth = dayDate.getMonth() === month;
                const dateKey = formatDateKey(dayDate);
                const items = itemsByDate[dateKey] || [];

                // Determine CSS classes
                const classes = ['calendar-day'];
                if (!isCurrentMonth) classes.push('other-month');
                if (isTripDay) classes.push('trip-day');
                if (isSameDay(dayDate, tripStart)) classes.push('trip-start');
                if (isSameDay(dayDate, tripEnd)) classes.push('trip-end');

                html += `<div class="${classes.join(' ')}" data-date="${dateKey}">`;
                html += `<div class="calendar-day-number">${dayDate.getDate()}</div>`;

                if (isTripDay && items.length > 0) {
                    html += '<div class="calendar-day-items">';

                    // Show max 3 items
                    const visibleItems = items.slice(0, 3);
                    for (const item of visibleItems) {
                        html += buildCalendarItem(item, isEditable);
                    }

                    // Show "+N more" if there are hidden items
                    if (items.length > 3) {
                        const hiddenItems = items.slice(3).map(item => ({
                            title: item.title || 'Activity',
                            time: formatItemTime(item),
                            location: item.location || '',
                            category: (item.category || 'other').toLowerCase(),
                            website: item.website || '',
                            notes: (item.notes || '').substring(0, 200)
                        }));
                        const hiddenJson = escapeHtml(JSON.stringify(hiddenItems));
                        html += `<div class="calendar-item-more" data-hidden-items="${hiddenJson}">+${items.length - 3} more</div>`;
                    }

                    html += '</div>';
                }

                html += '</div>';
            }

            html += '</div>';
        }

        html += '</div></div></div>';
        return html;
    }

    /**
     * Build HTML for a single calendar item
     */
    function buildCalendarItem(item, isEditable) {
        const category = (item.category || 'other').toLowerCase();
        const title = item.title || 'Activity';
        const fullTitle = escapeHtml(title);
        const displayTitle = title.length > 25 ? title.substring(0, 22) + '...' : title;

        // Build data attributes for popup
        const timeStr = formatItemTime(item);
        const location = escapeHtml(item.location || '');
        const website = escapeHtml(item.website || '');
        const notes = escapeHtml((item.notes || '').substring(0, 200));

        // Add day/item index if editable
        const editableAttrs = isEditable && item._dayIndex !== undefined
            ? ` data-day-index="${item._dayIndex}" data-item-index="${item._itemIndex}"`
            : '';

        return `<div class="calendar-item ${category}" ` +
               `data-title="${fullTitle}" ` +
               `data-time="${timeStr}" ` +
               `data-location="${location}" ` +
               `data-category="${category}" ` +
               `data-website="${website}" ` +
               `data-notes="${notes}"${editableAttrs}>` +
               `${escapeHtml(displayTitle)}</div>`;
    }

    /**
     * Format item time string
     */
    function formatItemTime(item) {
        if (!item.time) return '';
        let timeStr = formatTime12Hour(item.time);
        if (item.end_time) {
            timeStr += ' - ' + formatTime12Hour(item.end_time);
        }
        return timeStr;
    }

    /**
     * Check if two dates are the same day
     */
    function isSameDay(date1, date2) {
        return date1.getFullYear() === date2.getFullYear() &&
               date1.getMonth() === date2.getMonth() &&
               date1.getDate() === date2.getDate();
    }

    /**
     * Get all weeks for a month (array of arrays of Date objects)
     * Each week starts on Sunday
     */
    function getMonthWeeks(year, month) {
        const weeks = [];
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);

        // Start from the Sunday of the week containing the first day
        let current = new Date(firstDay);
        current.setDate(current.getDate() - current.getDay());

        while (current <= lastDay || current.getDay() !== 0) {
            const week = [];
            for (let i = 0; i < 7; i++) {
                week.push(new Date(current));
                current.setDate(current.getDate() + 1);
            }
            weeks.push(week);

            // Stop if we've completed the week containing the last day
            if (week[6] >= lastDay && week[6].getMonth() !== month) {
                break;
            }
        }

        return weeks;
    }

    /**
     * Render calendar view
     * @param {Object} tripData - Trip data object
     * @param {string} tripData.start_date - Start date (YYYY-MM-DD)
     * @param {string} tripData.end_date - End date (YYYY-MM-DD)
     * @param {Array} tripData.days - Array of day objects with date and items
     * @param {Object} options - Rendering options
     * @param {boolean} options.editable - If true, include edit attributes
     */
    function render(tripData, options = {}) {
        const startDate = parseDate(tripData.start_date);
        const endDate = parseDate(tripData.end_date);

        if (!startDate || !endDate) {
            return `<div class="calendar-empty">
                <i class="fas fa-calendar-times"></i>
                <h3>No dates available</h3>
                <p>This trip doesn't have date information for a calendar view.</p>
            </div>`;
        }

        // Build items by date lookup
        const itemsByDate = {};
        if (tripData.days) {
            tripData.days.forEach((day, dayIndex) => {
                if (day.date && day.items) {
                    itemsByDate[day.date] = day.items.map((item, itemIndex) => ({
                        ...item,
                        _dayIndex: dayIndex,
                        _itemIndex: itemIndex
                    }));
                }
            });
        }

        let html = '<div class="calendar-view">';

        // Generate calendar for each month in the trip
        let currentMonth = new Date(startDate.getFullYear(), startDate.getMonth(), 1);
        const endMonth = new Date(endDate.getFullYear(), endDate.getMonth(), 1);

        while (currentMonth <= endMonth) {
            html += buildMonthCalendar(
                currentMonth.getFullYear(),
                currentMonth.getMonth(),
                startDate,
                endDate,
                itemsByDate,
                options
            );

            // Move to next month
            currentMonth.setMonth(currentMonth.getMonth() + 1);
        }

        html += '</div>';
        return html;
    }

    /**
     * Update a specific day's items in the calendar (for incremental updates)
     */
    function updateDay(container, dateStr, items, options = {}) {
        const dayCell = container.querySelector(`.calendar-day[data-date="${dateStr}"]`);
        if (!dayCell) return;

        // Remove existing items
        const existingItems = dayCell.querySelector('.calendar-day-items');
        if (existingItems) {
            existingItems.remove();
        }

        // Add new items if any
        if (items && items.length > 0) {
            const itemsHtml = '<div class="calendar-day-items">' +
                items.slice(0, 3).map(item => buildCalendarItem(item, options.editable)).join('') +
                (items.length > 3 ? `<div class="calendar-item-more" data-hidden-items="${escapeHtml(JSON.stringify(items.slice(3)))}">+${items.length - 3} more</div>` : '') +
                '</div>';

            dayCell.insertAdjacentHTML('beforeend', itemsHtml);
        }
    }

    // Public API
    return {
        render: render,
        updateDay: updateDay,
        formatTime12Hour: formatTime12Hour,
        getCategoryIcon: getCategoryIcon
    };
})();

// Export for module systems if available
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CalendarView;
}
