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

        // Click on icon to edit (allows text selection on content)
        const icon = item.querySelector('.item-icon');
        if (icon) {
            icon.addEventListener('click', (e) => {
                e.stopPropagation();
                editIdea(index);
            });
        }

        // Double-click anywhere on card to edit
        item.addEventListener('dblclick', (e) => {
            // Don't trigger if clicking buttons
            if (e.target.closest('.item-actions')) return;
            editIdea(index);
        });
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

        // Click on icon to edit (allows text selection on content)
        const icon = item.querySelector('.item-icon');
        if (icon) {
            icon.addEventListener('click', (e) => {
                e.stopPropagation();
                const dayIndex = parseInt(item.dataset.dayIndex);
                const itemIndex = parseInt(item.dataset.itemIndex);
                editItem(dayIndex, itemIndex);
            });
        }

        // Double-click anywhere on card to edit
        item.addEventListener('dblclick', (e) => {
            // Don't trigger if clicking buttons
            if (e.target.closest('.item-actions')) return;
            const dayIndex = parseInt(item.dataset.dayIndex);
            const itemIndex = parseInt(item.dataset.itemIndex);
            editItem(dayIndex, itemIndex);
        });
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

