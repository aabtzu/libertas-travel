/* Libertas - File Upload Handling */

/**
 * Initialize upload functionality
 */
function initUpload() {
    const uploadArea = document.getElementById('upload-area');
    const uploadInput = document.getElementById('upload-input');
    const uploadStatus = document.getElementById('upload-status');
    const urlInput = document.getElementById('url-input');
    const urlSubmit = document.getElementById('url-submit');

    if (!uploadArea || !uploadInput) return;

    // Click to browse - handle clicks on the upload area
    uploadArea.addEventListener('click', (e) => {
        // Don't trigger if clicking the URL input area
        if (e.target.closest('.url-import-section')) return;
        uploadInput.click();
    });

    // Also handle the upload button specifically
    const uploadBtn = uploadArea.querySelector('.upload-btn');
    if (uploadBtn) {
        uploadBtn.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent double trigger
            uploadInput.click();
        });
    }

    // File selected via input
    uploadInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    // Drag and drop events
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });

    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');

        if (e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    // URL import functionality
    if (urlSubmit && urlInput) {
        urlSubmit.addEventListener('click', () => {
            const url = urlInput.value.trim();
            if (url) {
                handleUrlImport(url);
            }
        });

        // Allow Enter key to submit URL
        urlInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const url = urlInput.value.trim();
                if (url) {
                    handleUrlImport(url);
                }
            }
        });
    }
}

/**
 * Handle uploaded file
 * @param {File} file - The uploaded file
 */
function handleFile(file) {
    const uploadStatus = document.getElementById('upload-status');
    const validTypes = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
        'text/html'
    ];
    const validExtensions = ['.pdf', '.xlsx', '.xls', '.html', '.htm'];

    // Check file type
    const fileName = file.name.toLowerCase();
    const hasValidExtension = validExtensions.some(ext => fileName.endsWith(ext));

    if (!hasValidExtension) {
        showStatus('error', `Invalid file type. Please upload a PDF, Excel, or HTML file.`);
        return;
    }

    // Show loading status
    showStatus('loading', `Processing "${file.name}"...`);

    // Upload file to server
    uploadFile(file);
}

/**
 * Upload file to server
 * @param {File} file - The file to upload
 */
function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    fetch('/api/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Ask user for trip name
            promptForTripName(data.title, data.link);
        } else {
            showStatus('error', data.error || 'Failed to import trip.');
        }
    })
    .catch(error => {
        console.error('Upload error:', error);
        showStatus('error', 'Failed to upload file. Make sure the server is running.');
    });
}

/**
 * Show upload status message
 * @param {string} type - Status type: 'loading', 'success', or 'error'
 * @param {string} message - Status message to display
 */
function showStatus(type, message) {
    const uploadStatus = document.getElementById('upload-status');
    if (!uploadStatus) return;

    uploadStatus.className = 'upload-status show ' + type;

    let icon = '';
    if (type === 'loading') {
        icon = '<span class="spinner"></span>';
    } else if (type === 'success') {
        icon = '<i class="fas fa-check-circle"></i>';
    } else if (type === 'error') {
        icon = '<i class="fas fa-exclamation-circle"></i>';
    }

    uploadStatus.innerHTML = icon + message;
}

/**
 * Handle URL import
 * @param {string} url - The URL to import from
 */
function handleUrlImport(url) {
    // Basic URL validation
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        showStatus('error', 'Please enter a valid URL starting with http:// or https://');
        return;
    }

    // Show loading status
    showStatus('loading', 'Importing from URL...');

    // Send URL to server
    fetch('/api/import-url', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url: url })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Clear the URL input
            const urlInput = document.getElementById('url-input');
            if (urlInput) urlInput.value = '';

            // Ask user for trip name
            promptForTripName(data.title, data.link);
        } else {
            showStatus('error', data.error || 'Failed to import from URL.');
        }
    })
    .catch(error => {
        console.error('URL import error:', error);
        showStatus('error', 'Failed to import from URL. Make sure the server is running and the URL is accessible.');
    });
}

/**
 * Prompt user for trip name after import using a custom modal
 */
function promptForTripName(suggestedName, link) {
    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-header">
                <i class="fas fa-check-circle" style="color: #27ae60; font-size: 2rem;"></i>
                <h3>Trip Imported Successfully!</h3>
            </div>
            <div class="modal-body">
                <p>Suggested name based on destination:</p>
                <input type="text" class="modal-input" id="trip-name-input" value="${suggestedName}">
            </div>
            <div class="modal-footer">
                <button class="modal-btn modal-btn-secondary" id="modal-cancel">Use Suggested</button>
                <button class="modal-btn modal-btn-primary" id="modal-save">Save</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    // Focus input and select all text
    const input = document.getElementById('trip-name-input');
    input.focus();
    input.select();

    // Handle save
    const saveTrip = () => {
        const newName = input.value.trim();
        overlay.remove();

        if (newName && newName !== suggestedName) {
            fetch('/api/rename-trip', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ link: link, newTitle: newName })
            })
            .then(response => response.json())
            .then(data => {
                showStatus('success', `Trip saved as "${newName}"`);
                setTimeout(() => window.location.reload(), 1500);
            })
            .catch(() => {
                showStatus('success', `Trip imported as "${suggestedName}"`);
                setTimeout(() => window.location.reload(), 1500);
            });
        } else {
            showStatus('success', `Trip "${suggestedName}" imported successfully!`);
            setTimeout(() => window.location.reload(), 1500);
        }
    };

    // Handle cancel (use suggested name)
    const useSuggested = () => {
        overlay.remove();
        showStatus('success', `Trip "${suggestedName}" imported successfully!`);
        setTimeout(() => window.location.reload(), 1500);
    };

    document.getElementById('modal-save').addEventListener('click', saveTrip);
    document.getElementById('modal-cancel').addEventListener('click', useSuggested);

    // Handle Enter key
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') saveTrip();
    });

    // Handle Escape key
    overlay.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') useSuggested();
    });
}

/**
 * Initialize trip card actions (edit, delete, copy)
 */
function initTripActions() {
    // Edit buttons
    document.querySelectorAll('.edit-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            editTrip(btn);
        });
    });

    // Delete buttons
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const link = btn.dataset.link;
            const wrapper = btn.closest('.trip-card-wrapper');
            const title = wrapper.querySelector('.trip-card-title')?.textContent || 'this trip';

            if (confirm(`Are you sure you want to delete "${title}"?\n\nThis action cannot be undone.`)) {
                deleteTrip(link, wrapper);
            }
        });
    });

    // Copy buttons
    document.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const link = btn.dataset.link;
            copyTrip(link);
        });
    });
}

/**
 * Edit a trip - navigate to full editor
 */
function editTrip(btn) {
    const link = btn.dataset.link;
    // Navigate to the full editor
    window.location.href = `/create.html?edit=${link}`;
}

/**
 * Quick edit trip metadata (title, dates, etc.)
 */
function quickEditTrip(btn) {
    const link = btn.dataset.link;
    const title = btn.dataset.title;
    const dates = btn.dataset.dates;
    const days = btn.dataset.days;
    const locations = btn.dataset.locations;
    const activities = btn.dataset.activities;

    // Create edit modal
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-header">
                <i class="fas fa-edit" style="color: #f39c12; font-size: 1.5rem;"></i>
                <h3>Edit Trip</h3>
            </div>
            <div class="modal-body">
                <div class="edit-form">
                    <div class="form-group">
                        <label for="edit-title">Trip Name</label>
                        <input type="text" class="modal-input" id="edit-title" value="${title}">
                    </div>
                    <div class="form-group">
                        <label for="edit-dates">Dates</label>
                        <input type="text" class="modal-input" id="edit-dates" value="${dates}">
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="edit-days">Days</label>
                            <input type="number" class="modal-input" id="edit-days" value="${days}" min="1">
                        </div>
                        <div class="form-group">
                            <label for="edit-locations">Locations</label>
                            <input type="number" class="modal-input" id="edit-locations" value="${locations}" min="1">
                        </div>
                        <div class="form-group">
                            <label for="edit-activities">Activities</label>
                            <input type="number" class="modal-input" id="edit-activities" value="${activities}" min="1">
                        </div>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn modal-btn-secondary" id="edit-cancel">Cancel</button>
                <button class="modal-btn modal-btn-primary" id="edit-save">Save Changes</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    // Focus title input
    const titleInput = document.getElementById('edit-title');
    titleInput.focus();
    titleInput.select();

    // Handle save
    const saveChanges = () => {
        const newData = {
            link: link,
            title: document.getElementById('edit-title').value.trim(),
            dates: document.getElementById('edit-dates').value.trim(),
            days: parseInt(document.getElementById('edit-days').value) || 1,
            locations: parseInt(document.getElementById('edit-locations').value) || 1,
            activities: parseInt(document.getElementById('edit-activities').value) || 1
        };

        overlay.remove();

        fetch('/api/update-trip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showStatus('success', 'Trip updated successfully');
                setTimeout(() => window.location.reload(), 1000);
            } else {
                showStatus('error', data.error || 'Failed to update trip');
            }
        })
        .catch(() => {
            showStatus('error', 'Failed to update trip');
        });
    };

    // Handle cancel
    const cancelEdit = () => {
        overlay.remove();
    };

    document.getElementById('edit-save').addEventListener('click', saveChanges);
    document.getElementById('edit-cancel').addEventListener('click', cancelEdit);

    // Handle Enter key in inputs
    overlay.querySelectorAll('input').forEach(input => {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') saveChanges();
        });
    });

    // Handle Escape key
    overlay.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') cancelEdit();
    });
}

/**
 * Delete a trip
 */
function deleteTrip(link, cardElement) {
    fetch('/api/delete-trip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ link: link })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Animate removal
            cardElement.style.transition = 'opacity 0.3s, transform 0.3s';
            cardElement.style.opacity = '0';
            cardElement.style.transform = 'scale(0.9)';
            setTimeout(() => {
                cardElement.remove();
                showStatus('success', 'Trip deleted successfully');
            }, 300);
        } else {
            showStatus('error', data.error || 'Failed to delete trip');
        }
    })
    .catch(error => {
        console.error('Delete error:', error);
        showStatus('error', 'Failed to delete trip');
    });
}

/**
 * Copy a trip (placeholder for future editor)
 */
function copyTrip(link) {
    fetch('/api/copy-trip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ link: link })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showStatus('success', data.message);
            // Future: Open trip editor with data.trip
        } else {
            showStatus('error', data.error || 'Failed to copy trip');
        }
    })
    .catch(error => {
        console.error('Copy error:', error);
        showStatus('error', 'Failed to copy trip');
    });
}

/**
 * Initialize view toggle (grid/list)
 */
function initViewToggle() {
    const toggleBtns = document.querySelectorAll('.view-toggle-btn');
    const tripsContainer = document.getElementById('trips-container');
    const publicTripsContainer = document.querySelector('.public-trips-grid');

    if (!toggleBtns.length || !tripsContainer) return;

    // Load saved preference
    const savedView = localStorage.getItem('tripsViewMode') || 'grid';
    setView(savedView, tripsContainer, publicTripsContainer, toggleBtns);

    toggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const view = btn.dataset.view;
            setView(view, tripsContainer, publicTripsContainer, toggleBtns);
            localStorage.setItem('tripsViewMode', view);
        });
    });
}

/**
 * Set the view mode
 */
function setView(view, container, publicContainer, buttons) {
    // Update main container class
    container.classList.remove('trips-grid', 'trips-list');
    container.classList.add(view === 'list' ? 'trips-list' : 'trips-grid');

    // Update public trips container class if it exists
    if (publicContainer) {
        publicContainer.classList.remove('trips-grid', 'trips-list');
        publicContainer.classList.add(view === 'list' ? 'trips-list' : 'trips-grid');
    }

    // Update button states
    buttons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });
}

// ==================== Share Modal Functions ====================

// Store current trip being shared
let currentShareLink = '';
let currentShareTitle = '';

/**
 * Open the share modal for a trip
 */
function openShareModal(link, title) {
    currentShareLink = link;
    currentShareTitle = title;

    const modal = document.getElementById('share-modal');
    const titleSpan = document.getElementById('share-trip-title');
    const userList = document.getElementById('user-list');

    if (!modal) return;

    titleSpan.textContent = title;
    userList.innerHTML = '<div class="loading">Loading users...</div>';

    modal.classList.add('show');

    // Load users
    fetch('/api/users', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.users.length > 0) {
                userList.innerHTML = data.users.map(user => `
                    <div class="user-item" onclick="shareWithUser(${user.id}, '${user.username}')">
                        <i class="fas fa-user"></i>
                        <span class="username">${user.username}</span>
                    </div>
                `).join('');
            } else {
                userList.innerHTML = '<div class="loading">No other users available</div>';
            }
        })
        .catch(() => {
            userList.innerHTML = '<div class="loading">Failed to load users</div>';
        });
}

/**
 * Close the share modal
 */
function closeShareModal() {
    const modal = document.getElementById('share-modal');
    if (modal) {
        modal.classList.remove('show');
    }
    currentShareLink = '';
    currentShareTitle = '';
}

/**
 * Share with a specific user
 */
function shareWithUser(userId, username) {
    fetch('/api/share-trip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            link: currentShareLink,
            targetUserId: userId
        })
    })
    .then(response => response.json())
    .then(data => {
        closeShareModal();
        if (data.success) {
            showStatus('success', `Trip shared with ${username}`);
        } else {
            showStatus('error', data.error || 'Failed to share trip');
        }
    })
    .catch(() => {
        closeShareModal();
        showStatus('error', 'Failed to share trip');
    });
}

/**
 * Share with all users
 */
function shareWithAll() {
    fetch('/api/share-trip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            link: currentShareLink,
            shareWithAll: true
        })
    })
    .then(response => response.json())
    .then(data => {
        closeShareModal();
        if (data.success) {
            showStatus('success', data.message || 'Trip shared with all users');
        } else {
            showStatus('error', data.error || 'Failed to share trip');
        }
    })
    .catch(() => {
        closeShareModal();
        showStatus('error', 'Failed to share trip');
    });
}

/**
 * Toggle public visibility of a trip
 */
function togglePublic(btn) {
    const link = btn.dataset.link;
    const isCurrentlyPublic = btn.dataset.public === 'true';
    const newPublicState = !isCurrentlyPublic;

    fetch('/api/toggle-public', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            link: link,
            isPublic: newPublicState
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update button state
            btn.dataset.public = newPublicState ? 'true' : 'false';
            btn.classList.toggle('active', newPublicState);
            btn.title = newPublicState ? 'Make private' : 'Make public';
            btn.innerHTML = newPublicState ? '<i class="fas fa-globe"></i>' : '<i class="fas fa-lock"></i>';

            // Update public badge (positioned at top-left of wrapper)
            const wrapper = btn.closest('.trip-card-wrapper');
            let badge = wrapper.querySelector('.public-badge');

            if (newPublicState && !badge) {
                badge = document.createElement('span');
                badge.className = 'public-badge';
                badge.innerHTML = '<i class="fas fa-globe"></i>';
                wrapper.insertBefore(badge, wrapper.firstChild);
            } else if (!newPublicState && badge) {
                badge.remove();
            }

            showStatus('success', data.message);
        } else {
            showStatus('error', data.error || 'Failed to update visibility');
        }
    })
    .catch(() => {
        showStatus('error', 'Failed to update visibility');
    });
}

/**
 * Initialize share and public toggle actions
 */
function initShareActions() {
    // Share buttons
    document.querySelectorAll('.share-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const link = btn.dataset.link;
            const title = btn.dataset.title;
            openShareModal(link, title);
        });
    });

    // Public toggle buttons
    document.querySelectorAll('.public-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            togglePublic(btn);
        });
    });

    // Close modal when clicking outside
    const modal = document.getElementById('share-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeShareModal();
            }
        });
    }

    // Close modal on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeShareModal();
        }
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initUpload();
    initTripActions();
    initViewToggle();
    initShareActions();
});
