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
const CATEGORY_ICONS = {
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
 * Initialize event listeners
 */
function initEventListeners() {
    // Create trip form
    const createForm = document.getElementById('create-trip-form');
    if (createForm) {
        createForm.addEventListener('submit', handleCreateTrip);
    }

    // Date field interactions (clear num_days when dates are set)
    document.getElementById('start-date')?.addEventListener('change', () => {
        document.getElementById('num-days').value = '';
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

    // Upload plan button
    document.getElementById('upload-plan-btn')?.addEventListener('click', () => {
        document.getElementById('plan-file-input').click();
    });
    document.getElementById('plan-file-input')?.addEventListener('change', handlePlanUpload);
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
        alert('Please enter a trip name');
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
                ideas: []
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
            alert(data.error || 'Failed to create trip');
        }
    } catch (error) {
        console.error('Create trip error:', error);
        alert('Failed to create trip. Please try again.');
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

            // Hide publish button if already published
            const publishBtn = document.getElementById('publish-btn');
            if (publishBtn) {
                if (!trip.is_draft) {
                    publishBtn.style.display = 'none';
                } else {
                    publishBtn.style.display = '';
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

    const start = new Date(currentTrip.start_date);
    const end = new Date(currentTrip.end_date);
    const days = [];

    let current = new Date(start);
    let dayNum = 1;

    while (current <= end) {
        days.push({
            day_number: dayNum,
            date: current.toISOString().split('T')[0],
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
 * Render items for a day (in user-arranged order via drag-and-drop)
 */
function renderDayItems(items, dayIndex) {
    if (!items || items.length === 0) {
        return '<div class="day-items-empty">Drop items here or click + to add</div>';
    }

    // Render items in array order - user can arrange via drag-and-drop
    return items.map((item, index) => {
        const iconClass = getItemIcon(item);
        const timeStr = item.time ? `<span><i class="fas fa-clock"></i> ${formatTime12Hour(item.time)}</span>` : '';
        const locationStr = item.location ? `<span><i class="fas fa-map-marker-alt"></i> ${item.location}</span>` : '';

        return `
            <div class="item-card ${item.category || 'other'}" data-day-index="${dayIndex}" data-item-index="${index}" draggable="true">
                <div class="item-icon ${item.category || 'other'}">
                    <i class="fas ${iconClass}"></i>
                </div>
                <div class="item-content">
                    <div class="item-title">${escapeHtml(item.title)}</div>
                    <div class="item-meta">
                        ${timeStr}
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

        return `
            <div class="item-card ${item.category || 'other'}" data-idea-index="${index}" draggable="true">
                <div class="item-icon ${item.category || 'other'}">
                    <i class="fas ${iconClass}"></i>
                </div>
                <div class="item-content">
                    <div class="item-title">${escapeHtml(item.title)}</div>
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
        const d = new Date(lastDay.date);
        d.setDate(d.getDate() + 1);
        newDate = d.toISOString().split('T')[0];

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
    if (!confirm('Delete this day and all its items?')) return;

    currentTrip.days.splice(index, 1);

    // Renumber remaining days
    currentTrip.days.forEach((day, i) => {
        day.day_number = i + 1;
    });

    renderDays();
    triggerAutoSave();
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

    const item = {
        title: document.getElementById('item-title').value.trim(),
        category: document.getElementById('item-category').value,
        time: document.getElementById('item-time').value || null,
        location: document.getElementById('item-location').value.trim() || null,
        notes: document.getElementById('item-notes').value.trim() || null
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

    // Populate the add item modal with existing values
    document.getElementById('item-title').value = item.title || '';
    document.getElementById('item-category').value = item.category || 'activity';
    document.getElementById('item-time').value = item.time || '';
    document.getElementById('item-location').value = item.location || '';
    document.getElementById('item-notes').value = item.notes || '';
    document.getElementById('item-target-day').value = dayIndex;

    // Update modal title
    document.querySelector('#add-item-modal h3').textContent = 'Edit Item';

    // Show modal
    document.getElementById('add-item-modal').classList.remove('hidden');

    // Change submit behavior to update instead of add
    const form = document.getElementById('add-item-form');
    const newForm = form.cloneNode(true);
    form.parentNode.replaceChild(newForm, form);

    newForm.addEventListener('submit', (e) => {
        e.preventDefault();

        // Update item with new values
        currentTrip.days[dayIndex].items[itemIndex] = {
            title: document.getElementById('item-title').value.trim(),
            category: document.getElementById('item-category').value,
            time: document.getElementById('item-time').value || null,
            location: document.getElementById('item-location').value.trim() || null,
            notes: document.getElementById('item-notes').value.trim() || null
        };

        hideAddItemModal();
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

    // Populate the modal with existing values
    document.getElementById('item-title').value = item.title || '';
    document.getElementById('item-category').value = item.category || 'activity';
    document.getElementById('item-time').value = item.time || '';
    document.getElementById('item-location').value = item.location || '';
    document.getElementById('item-notes').value = item.notes || '';
    document.getElementById('item-target-day').value = 'ideas';

    // Update modal title
    document.querySelector('#add-item-modal h3').textContent = 'Edit Idea';

    // Show modal
    document.getElementById('add-item-modal').classList.remove('hidden');

    // Change submit behavior to update instead of add
    const form = document.getElementById('add-item-form');
    const newForm = form.cloneNode(true);
    form.parentNode.replaceChild(newForm, form);

    newForm.addEventListener('submit', (e) => {
        e.preventDefault();

        // Update idea with new values
        currentTrip.ideas[ideaIndex] = {
            title: document.getElementById('item-title').value.trim(),
            category: document.getElementById('item-category').value,
            time: document.getElementById('item-time').value || null,
            location: document.getElementById('item-location').value.trim() || null,
            notes: document.getElementById('item-notes').value.trim() || null
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
 */
function addToIdeas(item) {
    currentTrip.ideas.push(item);
    renderIdeas();
    triggerAutoSave();
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
            // Add extracted items - place on correct day if date matches, otherwise to Ideas
            let addedToDay = 0;
            let addedToIdeas = 0;
            let placementDetails = [];

            data.items.forEach(item => {
                if (!item.title) return;

                const newItem = {
                    title: item.title,
                    category: item.category || 'other',
                    time: item.time || null,
                    location: item.location || null,
                    notes: item.notes || null
                };

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
                    }
                }

                // Try to place by day number if not placed by date
                if (!placed && item.day !== undefined && item.day !== null) {
                    let dayIndex = currentTrip.days.findIndex(day => day.day_number === item.day);

                    // If day doesn't exist, create it (and any days before it)
                    if (dayIndex === -1 && item.day > 0) {
                        // Ensure we have all days up to the requested day
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
                    newItem.date = item.date || null; // Keep date in ideas for reference
                    currentTrip.ideas.push(newItem);
                    addedToIdeas++;
                    if (item.date) {
                        placementDetails.push(`- **${item.title}** → Ideas (date ${item.date} not in trip)`);
                    } else {
                        placementDetails.push(`- **${item.title}** → Ideas (no date)`);
                    }
                }
            });

            // Sort each day's items by time after upload (timed items first, then untimed)
            currentTrip.days.forEach(day => {
                if (day.items && day.items.length > 1) {
                    day.items.sort((a, b) => {
                        if (a.time && !b.time) return -1;
                        if (!a.time && b.time) return 1;
                        if (a.time && b.time) return a.time.localeCompare(b.time);
                        return 0;
                    });
                }
            });

            renderDays();
            renderIdeas();
            triggerAutoSave();

            // Show success message in chat
            let summaryMsg = `Found **${data.items.length} item(s)** in "${file.name}":\n\n${placementDetails.join('\n')}`;
            if (addedToDay > 0 && addedToIdeas > 0) {
                summaryMsg += `\n\n${addedToDay} item(s) placed on matching days, ${addedToIdeas} added to Ideas.`;
            } else if (addedToDay > 0) {
                summaryMsg += `\n\nAll items placed on matching days!`;
            } else {
                summaryMsg += `\n\nItems added to Ideas pile - drag them to specific days.`;
            }
            addChatMessage('assistant', summaryMsg);

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

// ==================== Chat ====================

/**
 * Initialize chat
 */
function initChat() {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send-btn');

    sendBtn?.addEventListener('click', sendChatMessage);

    input?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });

    // Auto-resize textarea
    input?.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });

    // Quick suggestions
    document.querySelectorAll('.suggestion-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            input.value = chip.textContent;
            sendChatMessage();
        });
    });
}

/**
 * Show welcome message
 */
function showWelcomeMessage() {
    const welcomeText = `Welcome! I'm here to help you plan "${currentTrip.title}".

Ask me for recommendations like:
- "Best restaurants in Rome"
- "Top attractions to visit"
- "Hidden gems nearby"

I'll suggest places you can add to your itinerary!`;

    addChatMessage('assistant', welcomeText);
}

/**
 * Send a chat message
 */
async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();

    if (!message) return;

    addChatMessage('user', message);
    input.value = '';
    input.style.height = 'auto';

    showTypingIndicator();

    try {
        const response = await fetch('/api/create/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                message: message,
                history: currentTrip.chatHistory.slice(-10),
                trip_context: {
                    destination: currentTrip.title,
                    dates: currentTrip.start_date && currentTrip.end_date
                        ? `${currentTrip.start_date} to ${currentTrip.end_date}`
                        : '',
                    days: currentTrip.days,
                    ideas: currentTrip.ideas
                }
            })
        });

        hideTypingIndicator();

        const data = await response.json();

        if (data.success) {
            // Process any items to add directly
            if (data.add_items && data.add_items.length > 0) {
                processAddItems(data.add_items);
            }

            // Add response with suggested items
            addChatMessage('assistant', data.response, data.suggested_items);
        } else {
            // Show specific error message
            const errorMsg = data.error || 'Unknown error occurred';
            console.error('Chat API error:', errorMsg);
            if (response.status === 401) {
                addChatMessage('assistant', 'Your session has expired. Please refresh the page and log in again.');
            } else {
                addChatMessage('assistant', `Sorry, I encountered an error: ${errorMsg}`);
            }
        }
    } catch (error) {
        hideTypingIndicator();
        console.error('Chat error:', error);
        addChatMessage('assistant', 'Sorry, I couldn\'t connect to the server. Please check your connection and try again.');
    }
}

/**
 * Process items to add from chat (from add_items in response)
 */
function processAddItems(items) {
    if (!items || items.length === 0) return;

    items.forEach(item => {
        const newItem = {
            title: item.title || 'Untitled',
            category: item.category || 'activity',
            location: item.location || '',
            notes: item.notes || '',
            time: item.time || null
        };

        // Check if day is specified
        if (item.day !== undefined && item.day !== null) {
            const dayIndex = item.day - 1; // Convert 1-indexed to 0-indexed

            if (dayIndex >= 0 && dayIndex < currentTrip.days.length) {
                // Add to specific day
                if (!currentTrip.days[dayIndex].items) {
                    currentTrip.days[dayIndex].items = [];
                }

                // Insert in correct time order if item has a time
                if (newItem.time) {
                    const dayItems = currentTrip.days[dayIndex].items;
                    let insertIndex = dayItems.length; // Default to end

                    for (let i = 0; i < dayItems.length; i++) {
                        const existingTime = dayItems[i].time;
                        if (existingTime && newItem.time < existingTime) {
                            insertIndex = i;
                            break;
                        }
                    }

                    dayItems.splice(insertIndex, 0, newItem);
                } else {
                    // No time, add to end
                    currentTrip.days[dayIndex].items.push(newItem);
                }
            } else {
                // Day doesn't exist, add to ideas
                currentTrip.ideas.push(newItem);
            }
        } else {
            // No day specified, add to ideas pile
            currentTrip.ideas.push(newItem);
        }
    });

    // Re-render and save
    renderDays();
    renderIdeas();
    triggerAutoSave();
}

/**
 * Add a message to the chat
 */
function addChatMessage(role, content, suggestedItems = [], saveToHistory = true) {
    const messagesContainer = document.getElementById('chat-messages');

    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.innerHTML = role === 'assistant'
        ? '<i class="fas fa-feather-alt"></i>'
        : '<i class="fas fa-user"></i>';

    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.innerHTML = formatMessageContent(content);

    // Add suggested items with "Add to Ideas" buttons
    if (suggestedItems && suggestedItems.length > 0) {
        suggestedItems.forEach(item => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'suggestion-item';
            itemDiv.innerHTML = `
                <div class="suggestion-item-header">
                    <span class="suggestion-item-title">${escapeHtml(item.title)}</span>
                </div>
                ${item.notes ? `<div class="suggestion-item-notes">${escapeHtml(item.notes)}</div>` : ''}
                <button class="btn-add-to-ideas" onclick='addToIdeas(${JSON.stringify(item).replace(/'/g, "&#39;")})'>
                    <i class="fas fa-plus"></i> Add to Ideas
                </button>
            `;
            bubble.appendChild(itemDiv);
        });
    }

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(bubble);
    messagesContainer.appendChild(messageDiv);

    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // Save to history (only for new messages, not when loading)
    if (saveToHistory) {
        currentTrip.chatHistory.push({ role, content, suggestedItems });
        triggerAutoSave();
    }
}

/**
 * Load saved chat history
 */
function loadChatHistory() {
    const messagesContainer = document.getElementById('chat-messages');
    messagesContainer.innerHTML = ''; // Clear default messages

    if (currentTrip.chatHistory.length === 0) {
        // No history, show welcome message
        showWelcomeMessage();
        return;
    }

    // Replay all messages from history
    currentTrip.chatHistory.forEach(msg => {
        addChatMessage(msg.role, msg.content, msg.suggestedItems || [], false);
    });

    // Add a "continuing conversation" indicator
    const continueDiv = document.createElement('div');
    continueDiv.className = 'chat-continue-indicator';
    continueDiv.innerHTML = '<i class="fas fa-history"></i> Conversation restored. Continue asking questions below.';
    messagesContainer.appendChild(continueDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Format message content
 */
function formatMessageContent(content) {
    let formatted = content.replace(/\n/g, '<br>');
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');
    return formatted;
}

/**
 * Show typing indicator
 */
function showTypingIndicator() {
    const messagesContainer = document.getElementById('chat-messages');

    const indicator = document.createElement('div');
    indicator.id = 'typing-indicator';
    indicator.className = 'chat-message assistant';
    indicator.innerHTML = `
        <div class="avatar"><i class="fas fa-feather-alt"></i></div>
        <div class="bubble typing-indicator">
            <span></span><span></span><span></span>
        </div>
    `;

    messagesContainer.appendChild(indicator);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Hide typing indicator
 */
function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
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
 * Publish the trip (convert from draft)
 */
async function publishTrip() {
    if (!currentTrip.link) return;

    if (!confirm('Publish this trip? It will be visible in your trips list.')) return;

    try {
        // Save first
        await performAutoSave();

        const response = await fetch(`/api/trips/${currentTrip.link}/publish`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (data.success) {
            alert('Trip published successfully!');
            window.location.href = '/trips.html';
        } else {
            alert(data.error || 'Failed to publish trip');
        }
    } catch (error) {
        console.error('Publish error:', error);
        alert('Failed to publish trip. Please try again.');
    }
}

// ==================== Utilities ====================

/**
 * Format date for display
 */
function formatDate(dateStr) {
    const date = new Date(dateStr);
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

// ==================== Drag and Drop ====================

let draggedItem = null;
let draggedItemIndex = null;
let dragSource = null; // 'ideas' or day index

/**
 * Initialize drag and drop functionality
 */
function initDragDrop() {
    // Will be reinitialized when items are rendered
}

/**
 * Set up drag handlers for idea items
 */
function setupIdeaDragHandlers() {
    const ideaItems = document.querySelectorAll('#ideas-list .item-card');
    ideaItems.forEach((item, index) => {
        item.setAttribute('draggable', 'true');
        item.dataset.ideaIndex = index;

        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragend', handleDragEnd);
    });
}

/**
 * Set up drag handlers for day items
 */
function setupDayItemDragHandlers() {
    const dayItems = document.querySelectorAll('.day-items .item-card');
    dayItems.forEach(item => {
        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragend', handleDragEnd);
    });
}

/**
 * Set up drop zone handlers for day items containers
 */
function setupDayDropZones() {
    const dayContainers = document.querySelectorAll('.day-items');
    dayContainers.forEach(container => {
        container.addEventListener('dragover', handleDragOver);
        container.addEventListener('dragleave', handleDragLeave);
        container.addEventListener('drop', handleDrop);
    });

    // Also allow dropping back to ideas pile
    const ideasList = document.getElementById('ideas-list');
    if (ideasList) {
        ideasList.addEventListener('dragover', handleDragOver);
        ideasList.addEventListener('dragleave', handleDragLeave);
        ideasList.addEventListener('drop', handleDropToIdeas);
    }
}

/**
 * Handle drag start
 */
function handleDragStart(e) {
    draggedItem = e.target.closest('.item-card');
    if (!draggedItem) return;

    // Determine source
    if (draggedItem.dataset.ideaIndex !== undefined) {
        dragSource = 'ideas';
        draggedItemIndex = parseInt(draggedItem.dataset.ideaIndex);
    } else if (draggedItem.dataset.dayIndex !== undefined) {
        dragSource = parseInt(draggedItem.dataset.dayIndex);
        draggedItemIndex = parseInt(draggedItem.dataset.itemIndex);
    }

    draggedItem.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', ''); // Required for Firefox
}

/**
 * Handle drag end
 */
function handleDragEnd(e) {
    if (draggedItem) {
        draggedItem.classList.remove('dragging');
    }
    document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
    draggedItem = null;
    draggedItemIndex = null;
    dragSource = null;
}

/**
 * Handle drag over
 */
function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    e.currentTarget.classList.add('drag-over');
}

/**
 * Handle drag leave
 */
function handleDragLeave(e) {
    e.currentTarget.classList.remove('drag-over');
}

/**
 * Handle drop on a day
 */
function handleDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');

    const targetDayIndex = parseInt(e.currentTarget.dataset.dayIndex);
    if (isNaN(targetDayIndex)) return;

    // Find drop position based on mouse position relative to items
    const dropPosition = getDropPosition(e, targetDayIndex);

    let item;
    let sameDay = (typeof dragSource === 'number' && dragSource === targetDayIndex);

    if (dragSource === 'ideas') {
        // Moving from ideas to a day
        item = currentTrip.ideas[draggedItemIndex];
        currentTrip.ideas.splice(draggedItemIndex, 1);
    } else if (typeof dragSource === 'number') {
        // Moving from one day (could be same day for reorder)
        item = currentTrip.days[dragSource].items[draggedItemIndex];
        currentTrip.days[dragSource].items.splice(draggedItemIndex, 1);
    }

    if (item) {
        if (!currentTrip.days[targetDayIndex].items) {
            currentTrip.days[targetDayIndex].items = [];
        }

        // Adjust drop position if reordering within same day and dropping after original position
        let insertAt = dropPosition;
        if (sameDay && draggedItemIndex < dropPosition) {
            insertAt = dropPosition - 1;
        }

        // Insert at the calculated position
        currentTrip.days[targetDayIndex].items.splice(insertAt, 0, item);

        renderDays();
        renderIdeas();
        triggerAutoSave();
    }
}

/**
 * Get drop position within a day based on mouse Y position
 */
function getDropPosition(e, dayIndex) {
    const container = e.currentTarget;
    const items = container.querySelectorAll('.item-card:not(.dragging)');

    if (items.length === 0) return 0;

    const mouseY = e.clientY;

    for (let i = 0; i < items.length; i++) {
        const rect = items[i].getBoundingClientRect();
        const midY = rect.top + rect.height / 2;

        if (mouseY < midY) {
            return i;
        }
    }

    // Drop at end
    return currentTrip.days[dayIndex].items.length;
}

/**
 * Handle drop back to ideas pile
 */
function handleDropToIdeas(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');

    if (dragSource === 'ideas') return; // Already in ideas

    let item;

    if (typeof dragSource === 'number') {
        // Moving from a day to ideas
        item = currentTrip.days[dragSource].items[draggedItemIndex];
        currentTrip.days[dragSource].items.splice(draggedItemIndex, 1);
    }

    if (item) {
        currentTrip.ideas.push(item);
        renderDays();
        renderIdeas();
        triggerAutoSave();
    }
}

// ==================== Map View ====================

let tripMap = null;
let mapMarkers = [];

// Load geocode cache from localStorage for persistence
let geocodeCache = {};
try {
    const savedCache = localStorage.getItem('libertas_geocode_cache');
    if (savedCache) {
        geocodeCache = JSON.parse(savedCache);
    }
} catch (e) {
    console.warn('Could not load geocode cache from localStorage');
}

function saveGeocodeCache() {
    try {
        // Only keep the last 500 entries to prevent localStorage from getting too large
        const keys = Object.keys(geocodeCache);
        if (keys.length > 500) {
            const toRemove = keys.slice(0, keys.length - 500);
            toRemove.forEach(k => delete geocodeCache[k]);
        }
        localStorage.setItem('libertas_geocode_cache', JSON.stringify(geocodeCache));
    } catch (e) {
        console.warn('Could not save geocode cache to localStorage');
    }
}

// Category colors for map markers
const CATEGORY_COLORS = {
    'flight': '#3b82f6',
    'transport': '#f59e0b',
    'hotel': '#8b5cf6',
    'lodging': '#8b5cf6',
    'meal': '#ef4444',
    'activity': '#22c55e',
    'attraction': '#06b6d4',
    'other': '#6b7280'
};

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
            } else if (cat === 'transport') {
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
            lastNightStay = currentNightStay;
        } else if (lastNightStay) {
            const isLastDay = (day.day_number === lastDayNum);
            if (!isLastDay && !hasFlight) {
                currentNightStay = lastNightStay;
                isCarried = true;
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
 * Format items for a column cell
 */
function formatColumnItems(items, isNotes = false) {
    if (items.length === 0) {
        return '<span class="column-empty">-</span>';
    }

    return items.map(item => {
        const cat = (item.category || 'other').toLowerCase();
        const icon = getCategoryIcon(cat);
        let html = `<div class="column-item ${cat}">`;
        html += `<div class="column-item-title"><i class="fas ${icon} column-item-icon"></i> ${escapeHtml(item.title)}</div>`;
        if (item.time) {
            html += `<div class="column-item-time"><i class="fas fa-clock"></i> ${item.time}</div>`;
        }
        if (item.location && !isNotes) {
            html += `<div class="column-item-location"><i class="fas fa-map-marker-alt"></i> ${escapeHtml(item.location)}</div>`;
        }
        if (item.notes && isNotes) {
            html += `<div class="column-item-notes">${escapeHtml(item.notes)}</div>`;
        }
        html += '</div>';
        return html;
    }).join('');
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Get day of week from date string
 */
function getDayOfWeek(dateStr) {
    const date = new Date(dateStr + 'T12:00:00');
    return date.toLocaleDateString('en-US', { weekday: 'long' });
}

/**
 * Format date for display
 */
function formatDate(dateStr) {
    const date = new Date(dateStr + 'T12:00:00');
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/**
 * Update the day selector dropdown for map view
 */
function updateMapDaySelector() {
    const select = document.getElementById('map-day-select');
    if (!select) return;

    // Store current selection
    const currentValue = select.value;

    // Rebuild options
    select.innerHTML = '<option value="all">All Days</option>';
    currentTrip.days.forEach((day, index) => {
        const dateStr = day.date ? ` (${formatDateShort(day.date)})` : '';
        select.innerHTML += `<option value="${index}">Day ${day.day_number}${dateStr}</option>`;
    });

    // Restore selection if still valid
    if (currentValue && select.querySelector(`option[value="${currentValue}"]`)) {
        select.value = currentValue;
    }
}

/**
 * Format date for day selector
 */
function formatDateShort(dateStr) {
    const date = new Date(dateStr + 'T00:00:00');
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/**
 * Initialize the Leaflet map
 */
function initializeMap() {
    const mapContainer = document.getElementById('trip-map');
    const mapLoading = document.getElementById('map-loading');

    if (!mapContainer) return;

    // If map already exists, just update markers
    if (tripMap) {
        updateMapForDay();
        return;
    }

    // Default center (will be overridden by markers)
    const defaultCenter = [43.7696, 11.2558]; // Florence
    const defaultZoom = 13;

    // Create map
    tripMap = L.map('trip-map').setView(defaultCenter, defaultZoom);

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(tripMap);

    // Hide loading and update markers
    if (mapLoading) mapLoading.classList.add('hidden');
    updateMapForDay();
}

/**
 * Update map markers based on selected day
 */
async function updateMapForDay() {
    if (!tripMap) return;

    const select = document.getElementById('map-day-select');
    const selectedDay = select ? select.value : 'all';

    // Clear existing markers
    mapMarkers.forEach(marker => tripMap.removeLayer(marker));
    mapMarkers = [];

    // Collect items to show
    let itemsToShow = [];

    if (selectedDay === 'all') {
        currentTrip.days.forEach((day, dayIndex) => {
            (day.items || []).forEach(item => {
                itemsToShow.push({ ...item, dayIndex, dayNumber: day.day_number });
            });
        });
    } else {
        const dayIndex = parseInt(selectedDay);
        const day = currentTrip.days[dayIndex];
        if (day && day.items) {
            day.items.forEach(item => {
                itemsToShow.push({ ...item, dayIndex, dayNumber: day.day_number });
            });
        }
    }

    // Filter items with locations
    const itemsWithLocation = itemsToShow.filter(item => item.location || item.title);

    if (itemsWithLocation.length === 0) {
        showNoLocationsMessage();
        return;
    }

    // Geocode and add markers
    const bounds = [];

    // Get destination context from trip title or first item with explicit location
    const tripDestination = extractDestinationFromTrip();

    // Build geo queries and geocode in parallel for faster loading
    const geocodePromises = itemsWithLocation.map(async (item) => {
        const searchQuery = buildGeoQuery(item, tripDestination);
        const coords = await geocodeLocation(searchQuery);
        return { item, coords };
    });

    const results = await Promise.all(geocodePromises);

    // Add markers for successful geocodes
    for (const { item, coords } of results) {
        if (coords) {
            const marker = createMapMarker(item, coords);
            mapMarkers.push(marker);
            bounds.push([coords.lat, coords.lng]);
        }
    }

    // Fit map to markers
    if (bounds.length > 0) {
        if (bounds.length === 1) {
            tripMap.setView(bounds[0], 15);
        } else {
            tripMap.fitBounds(bounds, { padding: [50, 50] });
        }
    }
}

/**
 * Extract destination/city from trip context
 */
function extractDestinationFromTrip() {
    // First, try to find a city from items with explicit locations
    const allItems = [];
    currentTrip.days.forEach(day => {
        (day.items || []).forEach(item => {
            if (item.location) allItems.push(item.location);
        });
    });

    // Look for common city patterns in locations
    const cityPatterns = ['Florence', 'Rome', 'Venice', 'Milan', 'Naples', 'Paris',
        'London', 'Barcelona', 'Madrid', 'Amsterdam', 'Berlin', 'Vienna', 'Prague',
        'Lisbon', 'Dublin', 'Edinburgh', 'Athens', 'Istanbul', 'Tokyo', 'Kyoto',
        'New York', 'Los Angeles', 'San Francisco', 'Chicago', 'Boston', 'Seattle'];

    for (const loc of allItems) {
        for (const city of cityPatterns) {
            if (loc.toLowerCase().includes(city.toLowerCase())) {
                return city;
            }
        }
    }

    // Try extracting from trip title
    const title = currentTrip.title || '';
    for (const city of cityPatterns) {
        if (title.toLowerCase().includes(city.toLowerCase())) {
            return city;
        }
    }

    // Return trip title as fallback (might contain destination info)
    return title;
}

/**
 * Build a geocoding query with destination context
 */
function buildGeoQuery(item, destination) {
    const location = item.location || '';
    const title = item.title || '';

    // If location already contains a city/country, use it directly
    if (location && (location.includes(',') || location.length > 30)) {
        return location;
    }

    // If location exists but is short (just a place name), add destination
    if (location && destination) {
        // Check if destination is already in location
        if (!location.toLowerCase().includes(destination.toLowerCase())) {
            return `${location}, ${destination}`;
        }
        return location;
    }

    // Use title with destination context
    if (title && destination) {
        return `${title}, ${destination}`;
    }

    // Fallback
    return location || title;
}

/**
 * Geocode a location string to coordinates using Nominatim
 */
async function geocodeLocation(query) {
    if (!query) return null;

    // Check cache first
    const cacheKey = query.toLowerCase().trim();
    if (geocodeCache[cacheKey]) {
        return geocodeCache[cacheKey];
    }

    try {
        const response = await fetch(
            `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`,
            {
                headers: {
                    'User-Agent': 'Libertas Travel Planner'
                }
            }
        );

        const data = await response.json();

        if (data && data.length > 0) {
            const result = {
                lat: parseFloat(data[0].lat),
                lng: parseFloat(data[0].lon)
            };
            geocodeCache[cacheKey] = result;
            saveGeocodeCache();  // Persist to localStorage
            return result;
        }
    } catch (error) {
        console.error('Geocoding error:', error);
    }

    return null;
}

/**
 * Create a map marker for an item
 */
function createMapMarker(item, coords) {
    const color = CATEGORY_COLORS[item.category] || CATEGORY_COLORS.other;
    const iconClass = getItemIcon(item);

    // Create custom icon
    const customIcon = L.divIcon({
        className: 'leaflet-custom-marker',
        html: `<div style="width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3);background-color:${color};">
                   <i class="fas ${iconClass}" style="color:white;font-size:14px;"></i>
               </div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
        popupAnchor: [0, -16]
    });

    // Build popup content
    const timeStr = item.time ? `<div><i class="fas fa-clock"></i> ${formatTime12Hour(item.time)}</div>` : '';
    const locationStr = item.location ? `<div><i class="fas fa-map-marker-alt"></i> ${escapeHtml(item.location)}</div>` : '';
    const dayStr = item.dayNumber ? `<div class="marker-day">Day ${item.dayNumber}</div>` : '';

    const popupContent = `
        <div class="marker-popup">
            ${dayStr}
            <div class="marker-title">${escapeHtml(item.title)}</div>
            <div class="marker-meta">
                ${timeStr}
                ${locationStr}
            </div>
        </div>
    `;

    const marker = L.marker([coords.lat, coords.lng], { icon: customIcon })
        .addTo(tripMap)
        .bindPopup(popupContent);

    return marker;
}

/**
 * Show message when no locations are available
 */
function showNoLocationsMessage() {
    const mapContainer = document.getElementById('trip-map');
    if (!mapContainer) return;

    // Check if message already exists
    if (!mapContainer.querySelector('.map-no-locations')) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'map-no-locations';
        messageDiv.innerHTML = `
            <i class="fas fa-map-marked-alt"></i>
            <p>No locations to display.<br>Add items with locations to see them on the map.</p>
        `;
        mapContainer.appendChild(messageDiv);
    }
}

// Make functions available globally
window.switchTimelineTab = switchTimelineTab;
window.updateMapForDay = updateMapForDay;
