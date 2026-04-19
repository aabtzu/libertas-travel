/**
 * Autosave, publish, and preview for the trip editor.
 * Extracted from create.js — depends on globals: currentTrip, tripLink, etc.
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

// ==================== Write-up ====================

async function generateWriteup() {
    if (!currentTrip.link) return;

    const btn = document.getElementById('generate-writeup-btn');
    const resultDiv = document.getElementById('writeup-result');
    const textDiv = document.getElementById('writeup-text');

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';

    try {
        // Save first so the server has latest data
        await performAutoSave();

        const res = await fetch(`/api/trips/${currentTrip.link}/writeup`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
        });
        const data = await res.json();

        if (data.success && data.writeup) {
            textDiv.textContent = data.writeup;
            resultDiv.style.display = 'block';
            btn.innerHTML = '<i class="fas fa-pen-fancy"></i> Regenerate Write-up';
        } else {
            LibertasModal.alert(data.error || 'Failed to generate write-up');
            btn.innerHTML = '<i class="fas fa-pen-fancy"></i> Generate Write-up';
        }
    } catch (e) {
        console.error('Write-up error:', e);
        LibertasModal.alert('Failed to generate write-up');
        btn.innerHTML = '<i class="fas fa-pen-fancy"></i> Generate Write-up';
    }
    btn.disabled = false;
}

function copyWriteup() {
    const text = document.getElementById('writeup-text')?.textContent;
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById('copy-writeup-btn');
        btn.innerHTML = '<i class="fas fa-check"></i>';
        setTimeout(() => { btn.innerHTML = '<i class="fas fa-copy"></i>'; }, 1500);
    });
}

// escapeHtml() and formatTime12Hour() — defined in main.js


