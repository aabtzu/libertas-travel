/**
 * Libertas Create Trip - Visual trip editor with LLM chat
 */

// Global state
let currentTrip = {
    link: null,
    title: '',
    start_date: null,
    end_date: null,
    days: [],
    ideas: [],
    tips: [],
    chatHistory: []
};
const AUTOSAVE_DELAY = 2000;
let autoSaveTimer = null;

// Category icons mapping
// CATEGORY_ICONS and CATEGORY_COLORS are defined in main.js

// Valid category values for the dropdown
const VALID_CATEGORIES = ['activity', 'meal', 'hotel', 'attraction', 'flight', 'transport', 'train', 'bus', 'other'];

// Category normalization map (map aliases to valid values)
const CATEGORY_MAP = {
    'travel': 'flight',
    'air': 'flight',
    'plane': 'flight',
    'transportation': 'transport',
    'car': 'transport',
    'rail': 'train',
    'coach': 'bus',
    'lodging': 'hotel',
    'accommodation': 'hotel',
    'stay': 'hotel',
    'restaurant': 'meal',
    'food': 'meal',
    'dining': 'meal',
    'sightseeing': 'attraction',
    'museum': 'attraction',
    'tour': 'attraction',
    'event': 'activity'
};

/**
 * Normalize a category value to one of the valid dropdown options
 */
function normalizeCategory(category) {
    if (!category) return 'activity';
    const cat = category.toLowerCase().trim();
    if (VALID_CATEGORIES.includes(cat)) return cat;
    if (CATEGORY_MAP[cat]) return CATEGORY_MAP[cat];
    return 'other';
}

/**
 * Get the appropriate icon for an item based on category and content
 */
function getItemIcon(item) {
    const category = item.category || 'other';
    const titleLower = (item.title || '').toLowerCase();
    const notesLower = (item.notes || '').toLowerCase();
    const searchText = titleLower + ' ' + notesLower;

    // Check for specific transport types
    if (category === 'transport') {
        if (searchText.includes('train') || searchText.includes('rail') ||
            searchText.includes('trenitalia') || searchText.includes('eurostar') ||
            searchText.includes('amtrak') || searchText.includes('tgv')) {
            return 'fa-train';
        }
        if (searchText.includes('bus') || searchText.includes('coach')) {
            return 'fa-bus';
        }
        if (searchText.includes('ferry') || searchText.includes('boat') || searchText.includes('cruise')) {
            return 'fa-ship';
        }
        if (searchText.includes('taxi') || searchText.includes('uber') || searchText.includes('lyft')) {
            return 'fa-taxi';
        }
    }

    return CATEGORY_ICONS[category] || 'fa-calendar-day';
}

/**
 * Get the icon for a category (simple lookup)
 */
function getCategoryIcon(category) {
    return CATEGORY_ICONS[category] || 'fa-calendar-day';
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Create page initialized, tripLink:', tripLink);
    if (tripLink) {
        // Load existing trip
        loadTrip(tripLink);
    } else {
        // Show create dialog for new trip
        showCreateDialog();
    }

    initEventListeners();
    initChat();
    initDragDrop();
});

/**
 * Initialize mobile chat sidebar toggle
 */
function initMobileChatSidebar() {
    const sidebar = document.getElementById('chat-sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const fab = document.getElementById('mobile-chat-fab');
    const closeBtn = document.getElementById('sidebar-close-btn');

    if (!sidebar || !fab) return;

    function openSidebar() {
        sidebar.classList.add('open');
        overlay?.classList.add('visible');
        fab?.classList.add('hidden');
        document.body.style.overflow = 'hidden'; // Prevent background scroll
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        overlay?.classList.remove('visible');
        fab?.classList.remove('hidden');
        document.body.style.overflow = '';
    }

    // Open on FAB click
    fab.addEventListener('click', openSidebar);

    // Close on X button click
    closeBtn?.addEventListener('click', closeSidebar);

    // Close on overlay click
    overlay?.addEventListener('click', closeSidebar);

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebar.classList.contains('open')) {
            closeSidebar();
        }
    });
}

/**
 * Initialize event listeners
 */
function initEventListeners() {
    // Initialize mobile chat sidebar
    initMobileChatSidebar();

    // Create trip form
    const createForm = document.getElementById('create-trip-form');
    if (createForm) {
        createForm.addEventListener('submit', handleCreateTrip);
    }

    // Date field interactions (clear num_days when dates are set)
    document.getElementById('start-date')?.addEventListener('change', (e) => {
        document.getElementById('num-days').value = '';
        const endDateInput = document.getElementById('end-date');
        if (e.target.value) {
            // Set end date minimum to start date
            endDateInput.min = e.target.value;
            // If end date is empty or before start date, default to start date
            if (!endDateInput.value || endDateInput.value < e.target.value) {
                endDateInput.value = e.target.value;
            }
        }
    });
    document.getElementById('end-date')?.addEventListener('change', () => {
        document.getElementById('num-days').value = '';
    });
    document.getElementById('num-days')?.addEventListener('input', () => {
        document.getElementById('start-date').value = '';
        document.getElementById('end-date').value = '';
    });

    // Editor title change
    document.getElementById('editor-title')?.addEventListener('input', (e) => {
        currentTrip.title = e.target.value;
        triggerAutoSave();
    });

    // Editor date changes
    document.getElementById('editor-start-date')?.addEventListener('change', (e) => {
        currentTrip.start_date = e.target.value || null;
        const endDateInput = document.getElementById('editor-end-date');
        if (e.target.value) {
            // Set end date minimum to start date
            endDateInput.min = e.target.value;
            // If end date is empty or before start date, default to start date
            if (!endDateInput.value || endDateInput.value < e.target.value) {
                endDateInput.value = e.target.value;
                currentTrip.end_date = e.target.value;
            }
        }
        updateDays();
        triggerAutoSave();
    });
    document.getElementById('editor-end-date')?.addEventListener('change', (e) => {
        currentTrip.end_date = e.target.value || null;
        updateDays();
        triggerAutoSave();
    });

    // Add day button
    document.getElementById('add-day-btn')?.addEventListener('click', addDay);

    // Add idea button
    document.getElementById('add-idea-btn')?.addEventListener('click', () => showAddItemModal(null));

    // Tips
    document.getElementById('add-tip-btn')?.addEventListener('click', addTip);
    document.getElementById('tip-input')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') addTip();
    });

    // Fill links + Write-up
    document.getElementById('fill-links-btn')?.addEventListener('click', fillMissingLinks);
    document.getElementById('generate-writeup-btn')?.addEventListener('click', generateWriteup);
    document.getElementById('copy-writeup-btn')?.addEventListener('click', copyWriteup);

    // Preview button
    document.getElementById('preview-btn')?.addEventListener('click', previewTrip);

    // Publish button
    document.getElementById('publish-btn')?.addEventListener('click', publishTrip);

    // Add item modal
    document.getElementById('close-item-modal')?.addEventListener('click', hideAddItemModal);
    document.getElementById('cancel-item-btn')?.addEventListener('click', hideAddItemModal);
    document.getElementById('add-item-form')?.addEventListener('submit', handleAddItem);

    // Close item modal on Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const modal = document.getElementById('add-item-modal');
            if (modal && !modal.classList.contains('hidden')) {
                hideAddItemModal();
            }
        }
    });

    // Upload plan button
    document.getElementById('upload-plan-btn')?.addEventListener('click', () => {
        document.getElementById('plan-file-input').click();
    });
    document.getElementById('plan-file-input')?.addEventListener('change', handlePlanUpload);

    // Drag-drop file upload on editor area
    setupFileDragDrop();
}

/**
 * Set up drag-drop file upload on the editor
 */
function showCreateDialog() {
    document.getElementById('create-dialog').classList.remove('hidden');
    document.getElementById('editor-container').style.display = 'none';
}

/**
 * Hide the create dialog and show editor
 */
function hideCreateDialog() {
    document.getElementById('create-dialog').classList.add('hidden');
    document.getElementById('editor-container').style.display = 'flex';
}

/**
 * Handle create trip form submission
 */
async function handleCreateTrip(e) {
    e.preventDefault();

    const title = document.getElementById('trip-title').value.trim();
    const startDate = document.getElementById('start-date').value || null;
    const endDate = document.getElementById('end-date').value || null;
    const numDays = document.getElementById('num-days').value || null;

    if (!title) {
        LibertasModal.alert('Please enter a trip name');
        return;
    }

    try {
        const response = await fetch('/api/trips/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: title,
                start_date: startDate,
                end_date: endDate,
                num_days: numDays ? parseInt(numDays) : null
            })
        });

        const data = await response.json();

        if (data.success && data.trip) {
            // Update URL with trip link
            window.history.replaceState({}, '', `/create.html?link=${data.trip.link}`);
            tripLink = data.trip.link;

            // Set up current trip
            currentTrip = {
                link: data.trip.link,
                title: data.trip.title,
                start_date: data.trip.start_date,
                end_date: data.trip.end_date,
                days: [],
                ideas: [],
                chatHistory: []
            };

            // Initialize days if dates are set
            if (currentTrip.start_date && currentTrip.end_date) {
                initializeDays();
            } else if (numDays) {
                // Create placeholder days without dates
                for (let i = 0; i < parseInt(numDays); i++) {
                    currentTrip.days.push({
                        day_number: i + 1,
                        date: null,
                        items: []
                    });
                }
            }

            // Update editor UI
            updateEditorUI();
            hideCreateDialog();
            showWelcomeMessage();
        } else {
            LibertasModal.alert(data.error || 'Failed to create trip');
        }
    } catch (error) {
        console.error('Create trip error:', error);
        LibertasModal.alert('Failed to create trip. Please try again.');
    }
}

/**
 * Load an existing trip
 */
async function loadTrip(link) {
    try {
        const response = await fetch(`/api/trips/${link}/data`, {
            credentials: 'same-origin'
        });

        // Check if we got redirected to login or got an error
        if (!response.ok) {
            console.error('Failed to load trip:', response.status, response.statusText);
            tripLink = null;
            showCreateDialog();
            return;
        }

        const data = await response.json();

        if (data.success && data.trip) {
            const trip = data.trip;

            // Parse itinerary_data if it's a string
            let itineraryData = trip.itinerary_data;
            if (typeof itineraryData === 'string') {
                try {
                    itineraryData = JSON.parse(itineraryData);
                } catch (e) {
                    itineraryData = { days: [], ideas: [], chatHistory: [] };
                }
            }

            currentTrip = {
                link: trip.link,
                title: trip.title,
                start_date: trip.start_date,
                end_date: trip.end_date,
                is_draft: trip.is_draft,
                days: itineraryData?.days || [],
                ideas: itineraryData?.ideas || [],
                tips: itineraryData?.tips || [],
                writeup: itineraryData?.writeup || '',
                chatHistory: itineraryData?.chatHistory || []
            };

            updateEditorUI();
            hideCreateDialog();

            // Change publish button text for already-published trips
            const publishBtn = document.getElementById('publish-btn');
            if (publishBtn) {
                if (!trip.is_draft) {
                    publishBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Republish';
                    publishBtn.title = 'Regenerate trip HTML with latest changes';
                } else {
                    publishBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Publish';
                    publishBtn.title = '';
                }
            }

            // Load existing chat history
            loadChatHistory();
        } else {
            // Trip not found, show create dialog
            tripLink = null;
            showCreateDialog();
        }
    } catch (error) {
        console.error('Load trip error:', error);
        tripLink = null;
        showCreateDialog();
    }
}

/**
 * Initialize days based on start/end dates
 */
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
 * Update days when dates change
 */
function updateDays() {
    if (currentTrip.start_date && currentTrip.end_date) {
        // Preserve existing items
        const existingItems = {};
        currentTrip.days.forEach(day => {
            if (day.date) {
                existingItems[day.date] = day.items;
            }
        });

        initializeDays();

        // Restore items
        currentTrip.days.forEach(day => {
            if (existingItems[day.date]) {
                day.items = existingItems[day.date];
            }
        });

        renderDays();
    }
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
