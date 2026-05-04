/**
 * Autosave, publish, and preview for the trip editor.
 * Extracted from create.js, depends on globals: currentTrip, tripLink, etc.
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
                    tips: currentTrip.tips,
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
        ? 'Update the trip page with your latest changes?'
        : 'Save this trip? It will be added to your My Trips list.';

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
            const successMsg = isRepublish ? 'Trip updated!' : 'Trip saved! It\'s in your My Trips list now.';
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

// ==================== Fill Missing Links ====================

async function fillMissingLinks() {
    if (!currentTrip.link) return;

    const btn = document.getElementById('fill-links-btn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Finding links...';

    try {
        await performAutoSave();

        const res = await fetch(`/api/trips/${currentTrip.link}/fill-links`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
        });
        const data = await res.json();

        if (data.success) {
            // Reload trip data to get updated links
            const tripRes = await fetch(`/api/trips/${currentTrip.link}/data`);
            const tripData = await tripRes.json();
            if (tripData.trip?.itinerary_data) {
                currentTrip.ideas = tripData.trip.itinerary_data.ideas || [];
                currentTrip.days = tripData.trip.itinerary_data.days || [];
                renderDays();
                renderIdeas();
            }
            btn.innerHTML = `<i class="fas fa-check"></i> Found ${data.websites_added} websites, ${data.maps_added} maps`;
            setTimeout(() => { btn.innerHTML = '<i class="fas fa-link"></i> Fill Missing Links'; }, 3000);
        } else {
            btn.innerHTML = '<i class="fas fa-link"></i> Fill Missing Links';
            LibertasModal.alert(data.error || 'Failed to fill links');
        }
    } catch (e) {
        console.error('Fill links error:', e);
        btn.innerHTML = '<i class="fas fa-link"></i> Fill Missing Links';
    }
    btn.disabled = false;
}

// ==================== Write-up ====================

let _writeupAbortController = null;

async function generateWriteup() {
    if (!currentTrip.link) return;

    const btn = document.getElementById('generate-writeup-btn');
    const resultDiv = document.getElementById('writeup-result');
    const textDiv = document.getElementById('writeup-text');

    // If already generating, cancel it
    if (_writeupAbortController) {
        _writeupAbortController.abort();
        _writeupAbortController = null;
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-pen-fancy"></i> Generate Write-up';
        return;
    }

    btn.innerHTML = '<i class="fas fa-times"></i> Cancel';

    try {
        await performAutoSave();

        _writeupAbortController = new AbortController();
        const res = await fetch(`/api/trips/${currentTrip.link}/writeup`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            signal: _writeupAbortController.signal,
        });
        _writeupAbortController = null;
        const data = await res.json();

        if (data.success && data.writeup) {
            textDiv.innerHTML = mdToHtml(data.writeup);
            textDiv.dataset.raw = data.writeup;
            resultDiv.style.display = 'block';
            btn.innerHTML = '<i class="fas fa-pen-fancy"></i> Regenerate Write-up';
            // Auto-save the write-up so /w/ link serves it without regenerating
            saveWriteup(data.writeup);
        } else {
            LibertasModal.alert(data.error || 'Failed to generate write-up');
            btn.innerHTML = '<i class="fas fa-pen-fancy"></i> Generate Write-up';
        }
    } catch (e) {
        _writeupAbortController = null;
        if (e.name === 'AbortError') {
            // User cancelled, already handled above
            return;
        }
        console.error('Write-up error:', e);
        btn.innerHTML = '<i class="fas fa-pen-fancy"></i> Generate Write-up';
    }
}

function copyWriteup() {
    const text = document.getElementById('writeup-text')?.dataset.raw || document.getElementById('writeup-text')?.textContent;
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById('copy-writeup-btn');
        btn.innerHTML = '<i class="fas fa-check"></i>';
        setTimeout(() => { btn.innerHTML = '<i class="fas fa-copy"></i>'; }, 1500);
    });
}

// ==================== Write-up Edit & Save ====================

async function saveWriteup(text) {
    if (!currentTrip.link) return;
    // Save write-up into itinerary_data
    await fetch(`/api/trips/${currentTrip.link}/save`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            title: currentTrip.title,
            itinerary_data: {
                days: currentTrip.days,
                ideas: currentTrip.ideas,
                tips: currentTrip.tips,
                chatHistory: currentTrip.chatHistory,
                writeup: text,
            }
        })
    });
}

function editWriteup() {
    const textDiv = document.getElementById('writeup-text');
    const raw = textDiv.dataset.raw || textDiv.textContent;

    // Replace rendered HTML with editable textarea
    const editArea = document.createElement('textarea');
    editArea.id = 'writeup-edit-area';
    editArea.className = 'writeup-edit-area';
    editArea.value = raw;
    editArea.rows = Math.max(10, raw.split('\n').length + 2);
    textDiv.replaceWith(editArea);

    // Change buttons
    const editBtn = document.getElementById('edit-writeup-btn');
    editBtn.innerHTML = '<i class="fas fa-save"></i>';
    editBtn.title = 'Save edits';
    editBtn.onclick = saveWriteupEdits;
}

async function saveWriteupEdits() {
    const editArea = document.getElementById('writeup-edit-area');
    if (!editArea) return;

    const newText = editArea.value.trim();

    // Replace textarea with rendered view
    const textDiv = document.createElement('div');
    textDiv.className = 'writeup-text';
    textDiv.id = 'writeup-text';
    textDiv.innerHTML = mdToHtml(newText);
    textDiv.dataset.raw = newText;
    editArea.replaceWith(textDiv);

    // Restore edit button
    const editBtn = document.getElementById('edit-writeup-btn');
    editBtn.innerHTML = '<i class="fas fa-edit"></i>';
    editBtn.title = 'Edit write-up';
    editBtn.onclick = editWriteup;

    // Save to server
    await saveWriteup(newText);
    updateSaveStatus('saved');
}

// escapeHtml() and formatTime12Hour(), defined in main.js


