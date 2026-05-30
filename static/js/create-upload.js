/**
 * Upload and file import handlers for the trip editor.
 * Extracted from create.js, depends on globals: currentTrip, renderDays, triggerAutoSave, etc.
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
            // Empty extraction is rare now (the prompt covers articles + lists),
            // but fall through gracefully if it happens. Tell the user what
            // worked best historically without making them feel like the upload
            // path is broken.
            addChatMessage(
                'assistant',
                `I couldn't pull anything actionable out of **${file.name}**. ` +
                `Try a booking confirmation, an article that names specific places, ` +
                `or paste the trip details into chat directly.`
            );
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

    // Before placing items, extend the trip's date range to cover any uploaded
    // items whose dates fall outside (or when no dates exist yet). This means
    // uploaded flights/hotels land on the right day instead of the Ideas pile.
    const datedItems = data.items.filter(it => it.title && it.date);
    if (datedItems.length > 0) {
        const uploadDates = datedItems.map(it => it.date).sort();
        const uploadMin = uploadDates[0];
        const uploadMax = uploadDates[uploadDates.length - 1];

        if (!currentTrip.start_date || !currentTrip.end_date) {
            // Trip has no dates yet - seed from uploaded items
            currentTrip.start_date = uploadMin;
            currentTrip.end_date = uploadMax;
            const startInput = document.getElementById('editor-start-date');
            const endInput = document.getElementById('editor-end-date');
            if (startInput) startInput.value = uploadMin;
            if (endInput) endInput.value = uploadMax;
            // Build days array from scratch
            const start = new Date(uploadMin + 'T12:00:00');
            const end = new Date(uploadMax + 'T12:00:00');
            const MS = 86400000;
            const count = Math.round((end - start) / MS) + 1;
            currentTrip.days = [];
            for (let i = 0; i < count; i++) {
                const d = new Date(start);
                d.setDate(d.getDate() + i);
                currentTrip.days.push({ day_number: i + 1, date: _ymd(d), items: [] });
            }
        } else {
            // Extend existing range at either end
            if (uploadMin < currentTrip.start_date) _extendTripDatesForItem(uploadMin);
            if (uploadMax > currentTrip.end_date) _extendTripDatesForItem(uploadMax);
        }
    }

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

