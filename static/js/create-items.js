/**
 * Item CRUD operations for the trip editor.
 * Extracted from create.js, depends on globals: currentTrip, renderDays, renderIdeas, triggerAutoSave, etc.
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
    document.getElementById('item-maps-link').value = item.google_maps_link || '';
    document.getElementById('item-notes').value = item.notes || '';
    document.getElementById('item-exclude-map').checked = item.is_home_location || false;
    document.getElementById('item-target-day').value = dayIndex;

    newForm.addEventListener('submit', (e) => {
        e.preventDefault();

        // Update item, preserve coordinates from original
        currentTrip.days[dayIndex].items[itemIndex] = {
            title: document.getElementById('item-title').value.trim(),
            category: document.getElementById('item-category').value,
            time: document.getElementById('item-time').value || null,
            end_time: document.getElementById('item-end-time').value || null,
            end_date: document.getElementById('item-end-date').value || null,
            location: document.getElementById('item-location').value.trim() || null,
            website: document.getElementById('item-website').value.trim() || null,
            google_maps_link: document.getElementById('item-maps-link').value.trim() || null,
            notes: document.getElementById('item-notes').value.trim() || null,
            is_home_location: document.getElementById('item-exclude-map').checked,
            latitude: item.latitude || null,
            longitude: item.longitude || null,
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
    document.getElementById('item-maps-link').value = item.google_maps_link || '';
    document.getElementById('item-notes').value = item.notes || '';
    document.getElementById('item-exclude-map').checked = item.is_home_location || false;
    document.getElementById('item-target-day').value = 'ideas';

    newForm.addEventListener('submit', (e) => {
        e.preventDefault();

        // Update idea, preserve coordinates from original item
        currentTrip.ideas[ideaIndex] = {
            title: document.getElementById('item-title').value.trim(),
            category: document.getElementById('item-category').value,
            time: document.getElementById('item-time').value || null,
            end_time: document.getElementById('item-end-time').value || null,
            end_date: document.getElementById('item-end-date').value || null,
            location: document.getElementById('item-location').value.trim() || null,
            website: document.getElementById('item-website').value.trim() || null,
            google_maps_link: document.getElementById('item-maps-link').value.trim() || null,
            notes: document.getElementById('item-notes').value.trim() || null,
            is_home_location: document.getElementById('item-exclude-map').checked,
            latitude: item.latitude || null,
            longitude: item.longitude || null,
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

