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
function setupFileDragDrop() {
    const editorContainer = document.getElementById('editor-container');
    if (!editorContainer) return;

    // Prevent default drag behaviors on document
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        document.body.addEventListener(eventName, (e) => {
            // Only prevent default for file drags
            if (e.dataTransfer && e.dataTransfer.types.includes('Files')) {
                e.preventDefault();
                e.stopPropagation();
            }
        });
    });

    // Highlight drop zone on drag over
    editorContainer.addEventListener('dragenter', (e) => {
        if (e.dataTransfer && e.dataTransfer.types.includes('Files')) {
            editorContainer.classList.add('file-drag-over');
        }
    });

    editorContainer.addEventListener('dragover', (e) => {
        if (e.dataTransfer && e.dataTransfer.types.includes('Files')) {
            e.dataTransfer.dropEffect = 'copy';
            editorContainer.classList.add('file-drag-over');
        }
    });

    editorContainer.addEventListener('dragleave', (e) => {
        // Only remove if leaving the container entirely
        if (!editorContainer.contains(e.relatedTarget)) {
            editorContainer.classList.remove('file-drag-over');
        }
    });

    editorContainer.addEventListener('drop', (e) => {
        editorContainer.classList.remove('file-drag-over');

        if (e.dataTransfer && e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            handleDroppedFile(file);
        }
    });
}

/**
 * Handle a dropped file (same as upload but from drag-drop)
 */
async function handleDroppedFile(file) {
    // Check file type
    if (!LibertasUpload.isAllowed(file.name)) {
        addChatMessage('assistant', `Unsupported file type: **${file.name}**\n\nSupported formats: ${LibertasUpload.DESCRIPTION}`);
        return;
    }

    const uploadBtn = document.getElementById('upload-plan-btn');

    // Show processing indicator
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

    // Add processing message to chat
    addChatMessage('assistant', `Processing dropped file: **${file.name}**\n\nAnalyzing document for travel details...`, [], false);

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/create/upload-plan', {
            method: 'POST',
            credentials: 'same-origin',
            body: formData
        });

        const data = await response.json();

        if (data.success && data.items && data.items.length > 0) {
            // Process items same as handlePlanUpload
            processUploadedItems(data, file.name);
        } else if (data.error) {
            addChatMessage('assistant', `Could not extract travel items from **${file.name}**:\n\n${data.error}`);
        } else {
            addChatMessage('assistant', `No travel items found in **${file.name}**. Try uploading a booking confirmation, itinerary, or ticket.`);
        }
    } catch (error) {
        console.error('Drop upload error:', error);
        addChatMessage('assistant', `Failed to process **${file.name}**: ${error.message}`);
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = '<i class="fas fa-file-upload"></i> Upload Plan';
    }
}

/**
 * Show the create dialog
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

    container.innerHTML = currentTrip.ideas.map((item, index) => {
        const iconClass = getItemIcon(item);
        const websiteStr = item.website ? `<a href="${escapeHtml(item.website)}" target="_blank" onclick="event.stopPropagation()" title="Visit website"><i class="fas fa-external-link-alt"></i></a>` : '';

        return `
            <div class="item-card ${item.category || 'other'}" data-idea-index="${index}" draggable="true">
                <div class="item-icon ${item.category || 'other'}">
                    <i class="fas ${iconClass}"></i>
                </div>
                <div class="item-content">
                    <div class="item-title">${escapeHtml(item.title)} ${websiteStr}</div>
                    ${item.notes ? `<div class="item-meta">${escapeHtml(item.notes.substring(0, 50))}...</div>` : ''}
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
    }).join('');

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
function showDayPickerDialog(item, triggerButton) {
    // If no days exist, prompt to create a day first
    if (currentTrip.days.length === 0) {
        LibertasModal.alert('Please add at least one day to your trip first.');
        return;
    }

    // Create popup menu for day selection
    const existing = document.querySelector('.day-picker-popup');
    if (existing) existing.remove();

    const popup = document.createElement('div');
    popup.className = 'day-picker-popup';

    const header = document.createElement('div');
    header.className = 'day-picker-header';
    header.textContent = 'Add to which day?';
    popup.appendChild(header);

    const dayList = document.createElement('div');
    dayList.className = 'day-picker-list';

    currentTrip.days.forEach((day, index) => {
        const dayOption = document.createElement('button');
        dayOption.className = 'day-picker-option';
        const dateStr = day.date ? formatDate(day.date) : 'Date TBD';
        dayOption.innerHTML = `<strong>Day ${day.day_number}</strong><span>${dateStr}</span>`;
        dayOption.addEventListener('click', () => {
            addItemToDay(item, index);
            popup.remove();
            triggerButton.innerHTML = '<i class="fas fa-check"></i> Added!';
            triggerButton.disabled = true;
            triggerButton.classList.add('added');
        });
        dayList.appendChild(dayOption);
    });

    popup.appendChild(dayList);

    // Position popup near button
    document.body.appendChild(popup);
    const btnRect = triggerButton.getBoundingClientRect();
    popup.style.position = 'fixed';
    popup.style.top = `${btnRect.bottom + 5}px`;
    popup.style.left = `${btnRect.left}px`;

    // Ensure popup is within viewport
    const popupRect = popup.getBoundingClientRect();
    if (popupRect.right > window.innerWidth) {
        popup.style.left = `${window.innerWidth - popupRect.width - 10}px`;
    }
    if (popupRect.bottom > window.innerHeight) {
        popup.style.top = `${btnRect.top - popupRect.height - 5}px`;
    }

    // Close on click outside
    const closeHandler = (e) => {
        if (!popup.contains(e.target) && e.target !== triggerButton) {
            popup.remove();
            document.removeEventListener('click', closeHandler);
        }
    };
    setTimeout(() => document.addEventListener('click', closeHandler), 10);
}

/**
 * Add item to a specific day
 */
function addItemToDay(item, dayIndex) {
    if (dayIndex < 0 || dayIndex >= currentTrip.days.length) return false;

    // Check for duplicates
    const newTitle = (item.title || '').toLowerCase().trim();
    if (newTitle) {
        const isDuplicate = currentTrip.days.some(day =>
            (day.items || []).some(existing => (existing.title || '').toLowerCase().trim() === newTitle)
        );
        if (isDuplicate) {
            console.log('Duplicate item not added:', item.title);
            return false;
        }
    }

    if (!currentTrip.days[dayIndex].items) {
        currentTrip.days[dayIndex].items = [];
    }

    currentTrip.days[dayIndex].items.push({
        title: item.title,
        category: item.category || 'activity',
        location: item.location || null,
        website: item.website || null,
        notes: item.notes || null,
        time: item.time || null,
        end_time: item.end_time || null
    });

    renderDays();
    triggerAutoSave();
    return true;
}

/**
 * Show add item modal
 */
function showAddItemModal(targetDayIndex) {
    document.getElementById('add-item-modal').classList.remove('hidden');
    document.getElementById('item-target-day').value = targetDayIndex !== null ? targetDayIndex : 'ideas';

    // Clear form
    document.getElementById('add-item-form').reset();
}

/**
 * Hide add item modal
 */
function hideAddItemModal() {
    document.getElementById('add-item-modal').classList.add('hidden');
}

/**
 * Handle add item form submission
 */
function handleAddItem(e) {
    e.preventDefault();

    const titleVal = document.getElementById('item-title').value.trim();
    if (!titleVal) {
        document.getElementById('item-title').focus();
        return;
    }

    const item = {
        title: titleVal,
        category: document.getElementById('item-category').value,
        time: document.getElementById('item-time').value || null,
        end_time: document.getElementById('item-end-time').value || null,
        end_date: document.getElementById('item-end-date').value || null,
        location: document.getElementById('item-location').value.trim() || null,
        website: document.getElementById('item-website').value.trim() || null,
        notes: document.getElementById('item-notes').value.trim() || null,
        is_home_location: document.getElementById('item-exclude-map').checked
    };

    const targetDay = document.getElementById('item-target-day').value;

    if (targetDay === 'ideas') {
        currentTrip.ideas.push(item);
        renderIdeas();
    } else {
        const dayIndex = parseInt(targetDay);
        if (!currentTrip.days[dayIndex].items) {
            currentTrip.days[dayIndex].items = [];
        }
        currentTrip.days[dayIndex].items.push(item);
        sortDayItemsByTime(dayIndex);
        renderDays();
    }

    hideAddItemModal();
    triggerAutoSave();
}

/**
 * Delete an item from a day
 */
function deleteItem(dayIndex, itemIndex) {
    currentTrip.days[dayIndex].items.splice(itemIndex, 1);
    renderDays();
    triggerAutoSave();
}

/**
 * Edit an item in a day
 */
function editItem(dayIndex, itemIndex) {
    const item = currentTrip.days[dayIndex].items[itemIndex];
    if (!item) return;

    // Update modal title
    document.querySelector('#add-item-modal h3').textContent = 'Edit Item';

    // Show modal
    document.getElementById('add-item-modal').classList.remove('hidden');

    // Change submit behavior to update instead of add
    const form = document.getElementById('add-item-form');
    const newForm = form.cloneNode(true);
    form.parentNode.replaceChild(newForm, form);

    // Populate form values AFTER cloning (cloneNode doesn't preserve programmatic select values)
    document.getElementById('item-title').value = item.title || '';
    document.getElementById('item-category').value = normalizeCategory(item.category);
    document.getElementById('item-time').value = item.time || '';
    document.getElementById('item-end-time').value = item.end_time || '';
    document.getElementById('item-end-date').value = item.end_date || '';
    document.getElementById('item-location').value = item.location || '';
    document.getElementById('item-website').value = item.website || '';
    document.getElementById('item-notes').value = item.notes || '';
    document.getElementById('item-exclude-map').checked = item.is_home_location || false;
    document.getElementById('item-target-day').value = dayIndex;

    newForm.addEventListener('submit', (e) => {
        e.preventDefault();

        // Update item with new values
        currentTrip.days[dayIndex].items[itemIndex] = {
            title: document.getElementById('item-title').value.trim(),
            category: document.getElementById('item-category').value,
            time: document.getElementById('item-time').value || null,
            end_time: document.getElementById('item-end-time').value || null,
            end_date: document.getElementById('item-end-date').value || null,
            location: document.getElementById('item-location').value.trim() || null,
            website: document.getElementById('item-website').value.trim() || null,
            notes: document.getElementById('item-notes').value.trim() || null,
            is_home_location: document.getElementById('item-exclude-map').checked
        };

        hideAddItemModal();
        sortDayItemsByTime(dayIndex);
        renderDays();
        triggerAutoSave();

        // Restore normal add behavior
        restoreAddItemForm();
    });

    // Update cancel button
    document.getElementById('cancel-item-btn')?.addEventListener('click', () => {
        hideAddItemModal();
        restoreAddItemForm();
    });
}

/**
 * Restore normal add item form behavior
 */
function restoreAddItemForm() {
    // Reset modal title
    document.querySelector('#add-item-modal h3').textContent = 'Add Item';

    const form = document.getElementById('add-item-form');
    const newForm = form.cloneNode(true);
    form.parentNode.replaceChild(newForm, form);
    newForm.addEventListener('submit', handleAddItem);
    document.getElementById('cancel-item-btn')?.addEventListener('click', hideAddItemModal);
}

/**
 * Edit an idea in the ideas pile
 */
function editIdea(ideaIndex) {
    const item = currentTrip.ideas[ideaIndex];
    if (!item) return;

    // Update modal title
    document.querySelector('#add-item-modal h3').textContent = 'Edit Idea';

    // Show modal
    document.getElementById('add-item-modal').classList.remove('hidden');

    // Change submit behavior to update instead of add
    const form = document.getElementById('add-item-form');
    const newForm = form.cloneNode(true);
    form.parentNode.replaceChild(newForm, form);

    // Populate form values AFTER cloning (cloneNode doesn't preserve programmatic select values)
    document.getElementById('item-title').value = item.title || '';
    document.getElementById('item-category').value = normalizeCategory(item.category);
    document.getElementById('item-time').value = item.time || '';
    document.getElementById('item-end-time').value = item.end_time || '';
    document.getElementById('item-end-date').value = item.end_date || '';
    document.getElementById('item-location').value = item.location || '';
    document.getElementById('item-website').value = item.website || '';
    document.getElementById('item-notes').value = item.notes || '';
    document.getElementById('item-exclude-map').checked = item.is_home_location || false;
    document.getElementById('item-target-day').value = 'ideas';

    newForm.addEventListener('submit', (e) => {
        e.preventDefault();

        // Update idea with new values
        currentTrip.ideas[ideaIndex] = {
            title: document.getElementById('item-title').value.trim(),
            category: document.getElementById('item-category').value,
            time: document.getElementById('item-time').value || null,
            end_time: document.getElementById('item-end-time').value || null,
            end_date: document.getElementById('item-end-date').value || null,
            location: document.getElementById('item-location').value.trim() || null,
            website: document.getElementById('item-website').value.trim() || null,
            notes: document.getElementById('item-notes').value.trim() || null,
            is_home_location: document.getElementById('item-exclude-map').checked
        };

        hideAddItemModal();
        renderIdeas();
        triggerAutoSave();

        // Restore normal add behavior
        restoreAddItemForm();
    });

    // Update cancel button
    document.getElementById('cancel-item-btn')?.addEventListener('click', () => {
        hideAddItemModal();
        restoreAddItemForm();
    });
}

/**
 * Delete an idea
 */
function deleteIdea(index) {
    currentTrip.ideas.splice(index, 1);
    renderIdeas();
    triggerAutoSave();
}

/**
 * Add item to ideas pile (used by chat)
 * Returns true if added, false if duplicate
 */
function addToIdeas(item) {
    // Check for duplicates before adding
    const newTitle = (item.title || '').toLowerCase().trim();
    if (newTitle) {
        // Check against ideas
        const isDuplicateInIdeas = currentTrip.ideas.some(
            existing => (existing.title || '').toLowerCase().trim() === newTitle
        );
        if (isDuplicateInIdeas) {
            console.log('Duplicate item not added (already in ideas):', item.title);
            return false;
        }
        // Check against day items
        const isDuplicateInDays = currentTrip.days.some(day =>
            (day.items || []).some(
                existing => (existing.title || '').toLowerCase().trim() === newTitle
            )
        );
        if (isDuplicateInDays) {
            console.log('Duplicate item not added (already in a day):', item.title);
            return false;
        }
    }

    currentTrip.ideas.push(item);
    renderIdeas();
    triggerAutoSave();
    return true;
}

// ==================== Plan Upload ====================

/**
 * Handle file upload for plans/reservations
 */
async function handlePlanUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Reset the input so same file can be uploaded again
    e.target.value = '';

    const uploadBtn = document.getElementById('upload-plan-btn');
    const ideasList = document.getElementById('ideas-list');

    // Show processing indicator
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

    // Add processing message to chat
    addChatMessage('assistant', `Processing uploaded file: **${file.name}**\n\nAnalyzing document for travel details...`, [], false);

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/create/upload-plan', {
            method: 'POST',
            credentials: 'same-origin',
            body: formData
        });

        const data = await response.json();

        if (data.success && data.items && data.items.length > 0) {
            processUploadedItems(data, file.name);
        } else if (data.success && (!data.items || data.items.length === 0)) {
            addChatMessage('assistant', `I couldn't find any travel-related items in "${file.name}". Try uploading a confirmation email, booking PDF, or screenshot of your reservation.`);
        } else {
            addChatMessage('assistant', `Error processing "${file.name}": ${data.error || 'Unknown error'}`);
        }

    } catch (error) {
        console.error('Upload error:', error);
        addChatMessage('assistant', `Failed to upload "${file.name}". Error: ${error.message || error}`);
    } finally {
        // Reset button
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = '<i class="fas fa-file-upload"></i> Upload Plan';
    }
}

/**
 * Process uploaded items from file (shared by drag-drop and file input)
 */
function processUploadedItems(data, fileName) {
    let addedToDay = 0;
    let addedToIdeas = 0;
    let placementDetails = [];

    data.items.forEach(item => {
        if (!item.title) return;

        const newItem = {
            title: item.title,
            category: item.category || 'other',
            time: item.time || null,
            end_time: item.end_time || null,
            end_date: item.end_date || null,
            location: item.location || null,
            website: item.website || null,
            notes: item.notes || null
        };
        console.log('processUploadedItems - newItem:', newItem.title, 'end_date:', newItem.end_date);

        // Try to find matching day by date or day number
        let placed = false;
        if (item.date) {
            const dayIndex = currentTrip.days.findIndex(day => day.date === item.date);
            if (dayIndex !== -1) {
                if (!currentTrip.days[dayIndex].items) {
                    currentTrip.days[dayIndex].items = [];
                }
                currentTrip.days[dayIndex].items.push(newItem);
                placed = true;
                addedToDay++;
                const dayNum = currentTrip.days[dayIndex].day_number;
                placementDetails.push(`- **${item.title}** → Day ${dayNum} (${item.date})`);

                // For car rentals with end_date, also create a return item on the drop-off day
                if (item.end_date && item.category === 'transport') {
                    const returnDayIndex = currentTrip.days.findIndex(day => day.date === item.end_date);
                    if (returnDayIndex !== -1) {
                        const returnItem = {
                            title: `Return: ${item.title}`,
                            category: 'transport',
                            time: item.end_time || null,
                            location: item.location,
                            notes: item.notes
                        };
                        if (!currentTrip.days[returnDayIndex].items) {
                            currentTrip.days[returnDayIndex].items = [];
                        }
                        currentTrip.days[returnDayIndex].items.push(returnItem);
                        addedToDay++;
                        const returnDayNum = currentTrip.days[returnDayIndex].day_number;
                        placementDetails.push(`- **Return: ${item.title}** → Day ${returnDayNum} (${item.end_date})`);
                    }
                }
            }
        }

        // Try to place by day number if not placed by date
        if (!placed && item.day !== undefined && item.day !== null) {
            let dayIndex = currentTrip.days.findIndex(day => day.day_number === item.day);

            // If day doesn't exist, create it (and any days before it)
            if (dayIndex === -1 && item.day > 0) {
                while (currentTrip.days.length < item.day) {
                    currentTrip.days.push({
                        day_number: currentTrip.days.length + 1,
                        date: null,
                        items: []
                    });
                }
                dayIndex = currentTrip.days.findIndex(day => day.day_number === item.day);
            }

            if (dayIndex !== -1) {
                if (!currentTrip.days[dayIndex].items) {
                    currentTrip.days[dayIndex].items = [];
                }
                currentTrip.days[dayIndex].items.push(newItem);
                placed = true;
                addedToDay++;
                placementDetails.push(`- **${item.title}** → Day ${item.day}`);
            }
        }

        // If no date/day match, add to Ideas pile
        if (!placed) {
            newItem.date = item.date || null;
            currentTrip.ideas.push(newItem);
            addedToIdeas++;
            if (item.date) {
                placementDetails.push(`- **${item.title}** → Ideas (date ${item.date} not in trip)`);
            } else {
                placementDetails.push(`- **${item.title}** → Ideas (no date)`);
            }
        }
    });

    // Sort each day's items by time
    currentTrip.days.forEach((day, index) => sortDayItemsByTime(index));

    renderDays();
    renderIdeas();
    triggerAutoSave();

    // Show success message in chat
    let summaryMsg = `Found **${data.items.length} item(s)** in "${fileName}":\n\n${placementDetails.join('\n')}`;
    if (addedToDay > 0 && addedToIdeas > 0) {
        summaryMsg += `\n\n${addedToDay} item(s) placed on matching days, ${addedToIdeas} added to Ideas.`;
    } else if (addedToDay > 0) {
        summaryMsg += `\n\nAll items placed on matching days!`;
    } else {
        summaryMsg += `\n\nItems added to Ideas pile - drag them to specific days.`;
    }
    addChatMessage('assistant', summaryMsg);
}

// ==================== Auto-Save ====================

/**
 * Trigger auto-save with debounce
 */
function triggerAutoSave() {
    if (autoSaveTimer) clearTimeout(autoSaveTimer);
    updateSaveStatus('pending');
    autoSaveTimer = setTimeout(performAutoSave, AUTOSAVE_DELAY);
}

/**
 * Perform the actual save
 */
async function performAutoSave() {
    if (!currentTrip.link) return;

    updateSaveStatus('saving');

    try {
        const response = await fetch(`/api/trips/${currentTrip.link}/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: currentTrip.title,
                itinerary_data: {
                    days: currentTrip.days,
                    ideas: currentTrip.ideas,
                    chatHistory: currentTrip.chatHistory
                }
            })
        });

        const data = await response.json();
        updateSaveStatus(data.success ? 'saved' : 'error');
    } catch (error) {
        console.error('Auto-save error:', error);
        updateSaveStatus('error');
    }
}

/**
 * Update save status indicator
 */
function updateSaveStatus(status) {
    const statusEl = document.getElementById('save-status');

    statusEl.classList.remove('saving', 'error');

    switch (status) {
        case 'pending':
            statusEl.innerHTML = '<i class="fas fa-circle" style="color: #f39c12;"></i><span>Unsaved</span>';
            break;
        case 'saving':
            statusEl.classList.add('saving');
            statusEl.innerHTML = '<i class="fas fa-spinner"></i><span>Saving...</span>';
            break;
        case 'saved':
            statusEl.innerHTML = '<i class="fas fa-check-circle"></i><span>Saved</span>';
            break;
        case 'error':
            statusEl.classList.add('error');
            statusEl.innerHTML = '<i class="fas fa-exclamation-circle"></i><span>Save failed</span>';
            break;
    }
}


// ==================== Preview & Publish ====================

/**
 * Preview the trip
 */
function previewTrip() {
    if (!currentTrip.link) return;
    window.open(`/trip/${currentTrip.link}`, '_blank');
}

/**
 * Publish the trip (convert from draft, or republish existing)
 */
async function publishTrip() {
    if (!currentTrip.link) return;

    const isRepublish = !currentTrip.is_draft;
    const confirmMsg = isRepublish
        ? 'Republish this trip? This will regenerate the trip page with your latest changes.'
        : 'Publish this trip? It will be visible in your trips list.';

    const confirmed = await LibertasModal.confirm(confirmMsg);
    if (!confirmed) return;

    try {
        // Save first
        await performAutoSave();

        const response = await fetch(`/api/trips/${currentTrip.link}/publish`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (data.success) {
            const successMsg = isRepublish ? 'Trip republished successfully!' : 'Trip published successfully!';
            await LibertasModal.alert(successMsg);
            if (isRepublish) {
                // For republish, open the trip view to see changes
                window.open(`/trip/${currentTrip.link}`, '_blank');
            } else {
                window.location.href = '/trips.html';
            }
        } else {
            LibertasModal.alert(data.error || 'Failed to publish trip');
        }
    } catch (error) {
        console.error('Publish error:', error);
        LibertasModal.alert('Failed to publish trip. Please try again.');
    }
}

// ==================== Utilities ====================

/**
 * Format date for display
 */
function formatDate(dateStr) {
    const date = new Date(dateStr + 'T12:00:00');
    return date.toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric'
    });
}

/**
 * Format time from 24-hour to 12-hour format
 */
function formatTime12Hour(time24) {
    if (!time24) return '';
    const [hours, minutes] = time24.split(':');
    const hour = parseInt(hours, 10);
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const hour12 = hour % 12 || 12;
    return `${hour12}:${minutes} ${ampm}`;
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

