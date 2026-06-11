/* Create Trip, Day rendering, item rendering, tips, ideas, day add/delete (split from create.js) */

function initializeDays() {
    if (!currentTrip.start_date || !currentTrip.end_date) return;

    // Use noon to avoid UTC midnight timezone rollover (the classic off-by-one bug)
    const start = new Date(currentTrip.start_date + 'T12:00:00');
    const end = new Date(currentTrip.end_date + 'T12:00:00');
    const days = [];

    let current = new Date(start);
    let dayNum = 1;

    while (current <= end) {
        const yyyy = current.getFullYear();
        const mm = String(current.getMonth() + 1).padStart(2, '0');
        const dd = String(current.getDate()).padStart(2, '0');
        days.push({
            day_number: dayNum,
            date: `${yyyy}-${mm}-${dd}`,
            items: []
        });
        current.setDate(current.getDate() + 1);
        dayNum++;
    }

    currentTrip.days = days;
}

/**
 * Format a Date as YYYY-MM-DD without UTC rollover.
 */
function _ymd(date) {
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
}

/**
 * Fill gaps in a days array so every day number from 1 to max is present.
 * Trips parsed from flights often have only day 1 and day 4 with nothing
 * in between. Without this, the editor has no container for days 2 and 3.
 */
function _fillDayGaps(days, startDateStr) {
    if (!days || days.length === 0) return days;
    const maxDay = Math.max(...days.map(d => d.day_number || 0));
    if (maxDay <= 1) return days;
    const byNum = {};
    days.forEach(d => { byNum[d.day_number] = d; });
    const filled = [];
    const startDate = startDateStr ? new Date(startDateStr + 'T12:00:00') : null;
    for (let i = 1; i <= maxDay; i++) {
        if (byNum[i]) {
            filled.push(byNum[i]);
        } else {
            let date = null;
            if (startDate) {
                const d = new Date(startDate);
                d.setDate(d.getDate() + i - 1);
                date = _ymd(d);
            }
            filled.push({ day_number: i, date, items: [] });
        }
    }
    return filled;
}

/**
 * Resize the days array to match start/end dates.
 *
 * Returns true if applied, false if the user cancelled a destructive shrink.
 *
 * - Map items from old days to new days **by index, not by date**, this
 *   preserves item ↔ day-number across date shifts (the previous date-key
 *   match silently lost everything when start_date jumped to a new range).
 * - If shrinking, dropped days' items move to the Ideas Pile so they're
 *   recoverable, and we confirm first if any items would be moved.
 */
async function updateDays() {
    if (!currentTrip.start_date || !currentTrip.end_date) return true;

    const start = new Date(currentTrip.start_date + 'T12:00:00');
    const end = new Date(currentTrip.end_date + 'T12:00:00');
    if (isNaN(start) || isNaN(end) || end < start) return true;

    const newCount = Math.round((end - start) / 86400000) + 1;
    const oldDays = currentTrip.days || [];
    const oldCount = oldDays.length;

    // Confirm destructive shrink (only if dropped days have items)
    if (newCount < oldCount) {
        const droppedItems = oldDays
            .slice(newCount)
            .flatMap(d => d.items || []);
        if (droppedItems.length > 0) {
            const ok = await LibertasModal.confirm(
                `This change will remove ${oldCount - newCount} day${oldCount - newCount === 1 ? '' : 's'} from your trip. ` +
                `${droppedItems.length} item${droppedItems.length === 1 ? '' : 's'} will be moved to the Ideas Pile so you don't lose ${droppedItems.length === 1 ? 'it' : 'them'}.\n\nContinue?`,
                { danger: true }
            );
            if (!ok) return false;
            currentTrip.ideas = (currentTrip.ideas || []).concat(droppedItems);
        }
    }

    // Rebuild days by index, items move with their day_number, not their date
    const newDays = [];
    for (let i = 0; i < newCount; i++) {
        const d = new Date(start);
        d.setDate(d.getDate() + i);
        newDays.push({
            day_number: i + 1,
            date: _ymd(d),
            items: oldDays[i]?.items || [],
        });
    }
    currentTrip.days = newDays;

    renderDays();
    renderIdeas();
    return true;
}

/**
 * Auto-detect start/end dates from days that have dates
 */
function syncDatesFromDays() {
    if (!currentTrip.days || currentTrip.days.length === 0) return;

    // Extract all dates from days
    const dates = currentTrip.days
        .map(day => day.date)
        .filter(date => date && date.length > 0)
        .sort();

    if (dates.length > 0) {
        const newStartDate = dates[0];
        const newEndDate = dates[dates.length - 1];

        // Only update if dates changed
        if (currentTrip.start_date !== newStartDate || currentTrip.end_date !== newEndDate) {
            currentTrip.start_date = newStartDate;
            currentTrip.end_date = newEndDate;

            // Update UI
            document.getElementById('editor-start-date').value = newStartDate;
            document.getElementById('editor-end-date').value = newEndDate;

            triggerAutoSave();
        }
    }
}

/**
 * Update the editor UI with current trip data
 */
function updateEditorUI() {
    document.getElementById('editor-title').value = currentTrip.title;
    document.getElementById('editor-start-date').value = currentTrip.start_date || '';
    document.getElementById('editor-end-date').value = currentTrip.end_date || '';

    // Auto-detect dates from days if not already set
    if (!currentTrip.start_date || !currentTrip.end_date) {
        syncDatesFromDays();
    }

    renderDays();
    renderIdeas();
    renderTips();

    // Load saved write-up if it exists (stored on currentTrip by loadTrip)
    const savedWriteup = currentTrip.writeup;
    if (savedWriteup) {
        const resultDiv = document.getElementById('writeup-result');
        const textDiv = document.getElementById('writeup-text');
        const btn = document.getElementById('generate-writeup-btn');
        if (resultDiv && textDiv) {
            textDiv.innerHTML = mdToHtml(savedWriteup);
            textDiv.dataset.raw = savedWriteup;
            resultDiv.style.display = 'block';
            if (btn) btn.innerHTML = '<i class="fas fa-pen-fancy"></i> Regenerate Write-up';
        }
    }
}

/**
 * Render days in the timeline
 */
function renderDays() {
    const container = document.getElementById('days-container');
    container.innerHTML = '';

    if (currentTrip.days.length === 0) {
        container.innerHTML = `
            <div class="day-items-empty">
                <i class="fas fa-calendar-plus" style="font-size: 2rem; color: #ddd; margin-bottom: 10px;"></i>
                <p>No days yet. Add dates above or click + to add a day.</p>
            </div>
        `;
        return;
    }

    currentTrip.days.forEach((day, index) => {
        const dayCard = document.createElement('div');
        dayCard.className = 'day-card';
        dayCard.dataset.dayIndex = index;

        const dateStr = day.date ? formatDate(day.date) : 'Date TBD';

        dayCard.innerHTML = `
            <div class="day-header">
                <div>
                    <h4>Day ${day.day_number}</h4>
                    <span class="day-date">${dateStr}</span>
                </div>
                <div class="day-actions">
                    <button onclick="showAddItemModal(${index})" title="Add item">
                        <i class="fas fa-plus"></i>
                    </button>
                    <button onclick="deleteDay(${index})" title="Delete day">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
            <div class="day-items" data-day-index="${index}">
                ${renderDayItems(day.items, index)}
            </div>
        `;

        container.appendChild(dayCard);
    });

    // Set up drag handlers after rendering
    setupDayItemDragHandlers();
    setupDayDropZones();
}

/**
 * Sort day items by time (timed items first in chronological order, then untimed)
 */
function sortDayItemsByTime(dayIndex) {
    if (!currentTrip.days[dayIndex] || !currentTrip.days[dayIndex].items) return;
    const items = currentTrip.days[dayIndex].items;
    if (items.length > 1) {
        items.sort((a, b) => {
            if (a.time && !b.time) return -1;
            if (!a.time && b.time) return 1;
            if (a.time && b.time) return a.time.localeCompare(b.time);
            return 0;
        });
    }
}

/**
 * Render items for a day (sorted by time)
 */
function renderDayItems(items, dayIndex) {
    if (!items || items.length === 0) {
        return '<div class="day-items-empty">Drop items here or click + to add</div>';
    }

    // Render items in array order - user can arrange via drag-and-drop
    return items.map((item, index) => {
        const iconClass = getItemIcon(item);
        let timeStr = '';
        if (item.time) {
            timeStr = formatTime12Hour(item.time);
            // For items with end_date (multi-day rentals), don't show end_time here - it goes in return info
            if (item.end_time && !item.end_date) {
                const cat = (item.category || '').toLowerCase();
                const isTravel = (cat === 'travel' || cat === 'flight' || cat === 'transport' || cat === 'train' || cat === 'bus');
                const separator = isTravel ? ' → ' : ' - ';
                timeStr += separator + formatTime12Hour(item.end_time);
            }
            timeStr = `<span><i class="fas fa-clock"></i> ${timeStr}</span>`;
        }
        // Show return date for multi-day rentals (car rentals)
        let returnDateStr = '';
        if (item.end_date) {
            const endDate = new Date(item.end_date + 'T12:00:00');
            const returnDatePart = endDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            const returnTimePart = item.end_time ? ', ' + formatTime12Hour(item.end_time) : '';
            returnDateStr = `<span><i class="fas fa-calendar-check"></i> Return: ${returnDatePart}${returnTimePart}</span>`;
        }
        const locationStr = item.location ? `<span><i class="fas fa-map-marker-alt"></i> ${item.location}</span>` : '';
        const websiteStr = item.website ? `<a href="${escapeHtml(item.website)}" target="_blank" onclick="event.stopPropagation()" title="Visit website"><i class="fas fa-external-link-alt"></i></a>` : '';

        return `
            <div class="item-card ${item.category || 'other'}" data-day-index="${dayIndex}" data-item-index="${index}" draggable="true">
                <div class="item-icon ${item.category || 'other'}">
                    <i class="fas ${iconClass}"></i>
                </div>
                <div class="item-content">
                    <div class="item-title">${escapeHtml(item.title)} ${websiteStr}</div>
                    <div class="item-meta">
                        ${timeStr}
                        ${returnDateStr}
                        ${locationStr}
                    </div>
                </div>
                <div class="item-actions">
                    <button onclick="editItem(${dayIndex}, ${index})" title="Edit">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button onclick="deleteItem(${dayIndex}, ${index})" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Render tips list
 */
function renderTips() {
    const container = document.getElementById('tips-list');
    if (!container) return;

    if (!currentTrip.tips || currentTrip.tips.length === 0) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = currentTrip.tips.map((tip, i) => `
        <div class="tip-item">
            <span class="tip-text" ondblclick="editTip(${i})">${escapeHtml(tip)}</span>
            <button class="tip-edit" onclick="editTip(${i})" title="Edit"><i class="fas fa-pen"></i></button>
            <button class="tip-delete" onclick="deleteTip(${i})" title="Remove"><i class="fas fa-times"></i></button>
        </div>
    `).join('');
}

function addTip() {
    const input = document.getElementById('tip-input');
    const text = input.value.trim();
    if (!text) return;
    if (!currentTrip.tips) currentTrip.tips = [];
    currentTrip.tips.push(text);
    input.value = '';
    renderTips();
    triggerAutoSave();
}

function editTip(index) {
    const container = document.getElementById('tips-list');
    const items = container.querySelectorAll('.tip-item');
    const item = items[index];
    if (!item) return;

    const currentText = currentTrip.tips[index];
    item.innerHTML = `
        <textarea class="tip-edit-input" rows="3">${escapeHtml(currentText)}</textarea>
        <button class="btn-add-tip" onclick="saveTip(${index})"><i class="fas fa-check"></i></button>
    `;
    const input = item.querySelector('textarea');
    input.focus();
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') renderTips();
    });
}

function saveTip(index) {
    const input = document.querySelector('textarea.tip-edit-input');
    if (!input) return;
    const text = input.value.trim();
    if (text) {
        currentTrip.tips[index] = text;
    } else {
        currentTrip.tips.splice(index, 1);
    }
    renderTips();
    triggerAutoSave();
}

function deleteTip(index) {
    currentTrip.tips.splice(index, 1);
    renderTips();
    triggerAutoSave();
}

/**
 * Render ideas pile
 */
function renderIdeas() {
    const container = document.getElementById('ideas-list');
    const countEl = document.getElementById('ideas-count');

    countEl.textContent = `${currentTrip.ideas.length} items`;

    if (currentTrip.ideas.length === 0) {
        container.innerHTML = '<div class="ideas-empty"><p>Drag items here or add from chat suggestions</p></div>';
        setupDayDropZones(); // Still allow dropping to ideas even when empty
        return;
    }

    // Group ideas by category
    const groups = {};
    currentTrip.ideas.forEach((item, index) => {
        const cat = item.category || 'other';
        if (!groups[cat]) groups[cat] = [];
        groups[cat].push({item, index});
    });

    const categoryLabels = {
        meal: 'Restaurants', activity: 'Activities', attraction: 'Attractions',
        hotel: 'Hotels', flight: 'Flights', transport: 'Transport', other: 'Other'
    };

    let html = '';
    for (const [cat, entries] of Object.entries(groups)) {
        const label = categoryLabels[cat] || cat;
        const icon = CATEGORY_ICONS[cat] || 'fa-map-marker-alt';
        html += `<div class="ideas-group-header"><i class="fas ${icon}"></i> ${label} (${entries.length})</div>`;

        for (const {item, index} of entries) {
            const iconClass = getItemIcon(item);
            const websiteStr = item.website ? `<a href="${escapeHtml(item.website)}" target="_blank" onclick="event.stopPropagation()" title="Visit website"><i class="fas fa-external-link-alt"></i></a>` : '';
            const mapsStr = item.google_maps_link ? `<a href="${escapeHtml(item.google_maps_link)}" target="_blank" onclick="event.stopPropagation()" title="Google Maps"><i class="fas fa-map-marker-alt"></i></a>` : '';

            html += `
                <div class="item-card ${cat}" data-idea-index="${index}" draggable="true">
                    <div class="item-icon ${cat}">
                        <i class="fas ${iconClass}"></i>
                    </div>
                    <div class="item-content">
                        <div class="item-title">${escapeHtml(item.title)} ${websiteStr} ${mapsStr}</div>
                        ${item.location ? `<div class="item-location"><i class="fas fa-map-pin"></i> ${escapeHtml(item.location)}</div>` : ''}
                        ${item.notes ? `<div class="item-meta">${escapeHtml(item.notes.substring(0, 200))}</div>` : ''}
                    </div>
                    <div class="item-actions">
                        <button onclick="editIdea(${index})" title="Edit">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button onclick="deleteIdea(${index})" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `;
        }
    }

    container.innerHTML = html;

    // Set up drag handlers after rendering
    setupIdeaDragHandlers();
    setupDayDropZones();
}

/**
 * Add a new day
 */
function addDay() {
    const lastDay = currentTrip.days[currentTrip.days.length - 1];
    let newDate = null;

    if (lastDay && lastDay.date) {
        const d = new Date(lastDay.date + 'T12:00:00');
        d.setDate(d.getDate() + 1);
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        newDate = `${yyyy}-${mm}-${dd}`;

        // Also update end_date
        currentTrip.end_date = newDate;
        document.getElementById('editor-end-date').value = newDate;
    }

    currentTrip.days.push({
        day_number: currentTrip.days.length + 1,
        date: newDate,
        items: []
    });

    renderDays();
    triggerAutoSave();
}

/**
 * Delete a day
 */
function deleteDay(index) {
    LibertasModal.confirm('Delete this day and all its items?', { danger: true }).then(function(confirmed) {
        if (!confirmed) return;
        currentTrip.days.splice(index, 1);

        // Renumber remaining days
        currentTrip.days.forEach((day, i) => {
            day.day_number = i + 1;
        });

        renderDays();
        triggerAutoSave();
    });
}

/**
 * Show day picker dialog for adding item to itinerary
 */
