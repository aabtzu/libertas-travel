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

        const personalize = document.getElementById('personalize-checkbox')?.checked;
        const url = `/api/trips/${currentTrip.link}/writeup${personalize ? '?personalize=true' : ''}`;
        const res = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
        });
        const data = await res.json();

        if (data.success && data.writeup) {
            textDiv.innerHTML = mdToHtml(data.writeup);
            textDiv.dataset.raw = data.writeup;
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
    const text = document.getElementById('writeup-text')?.dataset.raw || document.getElementById('writeup-text')?.textContent;
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById('copy-writeup-btn');
        btn.innerHTML = '<i class="fas fa-check"></i>';
        setTimeout(() => { btn.innerHTML = '<i class="fas fa-copy"></i>'; }, 1500);
    });
}

// ==================== Style Profile ====================

function initStyleControls() {
    const checkbox = document.getElementById('personalize-checkbox');
    const setup = document.getElementById('style-setup');
    const saveBtn = document.getElementById('save-style-btn');

    if (!checkbox) return;

    // Check if user already has a style profile
    fetch('/api/trips/list').then(r => r.json()).then(data => {
        const hasProfile = (data.trips || []).some(t => t.link === '__style_profile__.html');
        if (hasProfile) {
            checkbox.parentElement.title = 'Write in your personal voice (style saved)';
        }
    }).catch(() => {});

    checkbox.addEventListener('change', () => {
        if (checkbox.checked) {
            // Check if profile exists
            fetch('/api/trips/__style_profile__.html/data').then(r => {
                if (r.ok) {
                    // Profile exists, just use it
                    setup.style.display = 'none';
                } else {
                    // No profile, show setup
                    setup.style.display = 'block';
                }
            }).catch(() => { setup.style.display = 'block'; });
        } else {
            setup.style.display = 'none';
        }
    });

    if (saveBtn) {
        saveBtn.addEventListener('click', async () => {
            const samples = document.getElementById('style-samples')?.value?.trim();
            if (!samples || samples.length < 50) {
                LibertasModal.alert('Paste at least a few sentences of your writing.');
                return;
            }

            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';

            try {
                const res = await fetch('/api/user/extract-style', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({samples}),
                });
                const data = await res.json();
                if (data.success) {
                    setup.style.display = 'none';
                    saveBtn.innerHTML = '<i class="fas fa-check"></i> Style saved';
                    LibertasModal.alert('Writing style saved! Your write-ups will now use your voice.');
                } else {
                    LibertasModal.alert(data.error || 'Failed to analyze style');
                    saveBtn.innerHTML = '<i class="fas fa-user-edit"></i> Save My Style';
                }
            } catch {
                saveBtn.innerHTML = '<i class="fas fa-user-edit"></i> Save My Style';
            }
            saveBtn.disabled = false;
        });
    }
}

// escapeHtml() and formatTime12Hour() — defined in main.js


