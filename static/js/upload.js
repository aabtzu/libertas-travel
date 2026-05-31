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
    if (!LibertasUpload.isAllowed(file.name)) {
        showStatus('error', `Unsupported file type. Supported: ${LibertasUpload.DESCRIPTION}`);
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
    // Build modal via DOM (not innerHTML) so an attacker-controlled
    // suggestedName from a parsed file can't break out of the value="..."
    // attribute and inject markup.
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
                <input type="text" class="modal-input" id="trip-name-input">
            </div>
            <div class="modal-footer">
                <button class="modal-btn modal-btn-secondary" id="modal-cancel">Use Suggested</button>
                <button class="modal-btn modal-btn-primary" id="modal-save">Save</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    // Set the input value via DOM property, safe regardless of contents
    const input = document.getElementById('trip-name-input');
    input.value = suggestedName || '';
    input.focus();
    input.select();

    // After import we send the user straight into the trip editor instead
    // of reloading the trips list. Lets them see what was imported and
    // add more items in one continuous flow (per Gene's feedback, where
    // a stop on /trips made him think each upload was a separate trip).
    const goToEditor = () => {
        // Flag the next page load so the editor can show a "you just
        // imported, here's how to add more" banner. sessionStorage clears
        // when the tab closes so it doesn't haunt future visits.
        try { sessionStorage.setItem('libertas_just_imported', '1'); } catch (e) {}
        window.location.href = `/create.html?edit=${encodeURIComponent(link)}`;
    };

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
            .then(() => {
                showStatus('success', `Trip saved as "${newName}". Opening editor...`);
                setTimeout(goToEditor, 800);
            })
            .catch(() => {
                showStatus('success', `Trip imported as "${suggestedName}". Opening editor...`);
                setTimeout(goToEditor, 800);
            });
        } else {
            showStatus('success', `Trip "${suggestedName}" imported. Opening editor...`);
            setTimeout(goToEditor, 800);
        }
    };

    // Handle cancel (use suggested name, still go to editor)
    const useSuggested = () => {
        overlay.remove();
        showStatus('success', `Trip "${suggestedName}" imported. Opening editor...`);
        setTimeout(goToEditor, 800);
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

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initUpload();
});
