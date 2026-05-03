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
 * Format a Date as YYYY-MM-DD without UTC rollover.
 * Mirrors `_ymd` in create-render.js — both files use date math.
 */
function _formatYmd(date) {
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
}

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

    // Editor date changes — picking a date should never silently shrink
    // the trip. If days already exist, shift the other end so the duration
    // is preserved; if shortening would drop items, updateDays() asks first
    // and parks them in the Ideas Pile.
    document.getElementById('editor-start-date')?.addEventListener('change', async (e) => {
        const newStart = e.target.value || null;
        const endInput = document.getElementById('editor-end-date');
        const oldStart = currentTrip.start_date;
        const oldEnd = currentTrip.end_date;
        const dayCount = currentTrip.days?.length || 0;
        const previousStart = oldStart;
        const previousEnd = oldEnd;

        if (!newStart) {
            currentTrip.start_date = null;
            triggerAutoSave();
            return;
        }

        endInput.min = newStart;

        if (oldStart && oldEnd) {
            // Both dates already set — shift end by the same delta as start
            const delta = Math.round(
                (new Date(newStart + 'T12:00:00') - new Date(oldStart + 'T12:00:00')) / 86400000
            );
            const newEndD = new Date(oldEnd + 'T12:00:00');
            newEndD.setDate(newEndD.getDate() + delta);
            currentTrip.end_date = _formatYmd(newEndD);
        } else if (dayCount > 1) {
            // No dates yet but days exist — anchor end at start + (N-1)
            const newEndD = new Date(newStart + 'T12:00:00');
            newEndD.setDate(newEndD.getDate() + dayCount - 1);
            currentTrip.end_date = _formatYmd(newEndD);
        } else if (!endInput.value || endInput.value < newStart) {
            // No days, no end yet — fall back to single-day default
            currentTrip.end_date = newStart;
        }

        currentTrip.start_date = newStart;
        endInput.value = currentTrip.end_date || '';

        const ok = await updateDays();
        if (ok === false) {
            // User cancelled the shrink — revert
            currentTrip.start_date = previousStart;
            currentTrip.end_date = previousEnd;
            e.target.value = previousStart || '';
            endInput.value = previousEnd || '';
            return;
        }
        triggerAutoSave();
    });
    document.getElementById('editor-end-date')?.addEventListener('change', async (e) => {
        const newEnd = e.target.value || null;
        const previousEnd = currentTrip.end_date;
        currentTrip.end_date = newEnd;
        const ok = await updateDays();
        if (ok === false) {
            currentTrip.end_date = previousEnd;
            e.target.value = previousEnd || '';
            return;
        }
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
