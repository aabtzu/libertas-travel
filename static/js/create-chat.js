// ==================== Chat ====================

/**
 * Initialize chat
 */
function initChat() {
    const input = document.getElementById('chat-input');

    // Use shared chat utilities for history and cancel support
    LibertasChat.init({
        inputId: 'chat-input',
        sendBtnId: 'chat-send-btn',
        onSend: handleChatMessage,
        onCancel: () => {
            hideTypingIndicator();
            addChatMessage('assistant', 'Request cancelled.');
        }
    });

    // Quick suggestions
    document.querySelectorAll('.suggestion-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            input.value = chip.textContent;
            // Trigger enter to let LibertasChat handle it
            input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
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
 * Handle a chat message (called by LibertasChat)
 */
async function handleChatMessage(message, abortController) {
    const input = document.getElementById('chat-input');

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
            }),
            signal: abortController.signal
        });

        hideTypingIndicator();

        const data = await response.json();

        if (data.success) {
            // Process any items to edit directly
            if (data.edit_items && data.edit_items.length > 0) {
                processEditItems(data.edit_items);
            }

            // Process any items to add directly
            if (data.add_items && data.add_items.length > 0) {
                processAddItems(data.add_items);
            }

            // Filter suggested items to exclude duplicates
            let suggestedItems = data.suggested_items || [];
            if (suggestedItems.length > 0) {
                suggestedItems = suggestedItems.filter(item => !isDuplicateItem(item.title));
            }

            // Fallback: if the LLM added items but sent no text, synthesize a confirmation
            // so the user never sees an empty bubble.
            let responseText = data.response;
            if (!responseText && data.add_items && data.add_items.length > 0) {
                const descriptions = data.add_items.map(it => {
                    const dayLabel = it.day ? ` (Day ${it.day})` : '';
                    const timeLabel = it.time ? ` at ${it.time}` : '';
                    return `**${it.title}**${dayLabel}${timeLabel}`;
                });
                responseText = `Added ${descriptions.join(', ')} to your trip.`;
            }

            // Add response with suggested items (filtered)
            addChatMessage('assistant', responseText, suggestedItems);
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
        if (error.name === 'AbortError') {
            throw error; // Re-throw to let LibertasChat handle it
        }
        console.error('Chat error:', error);
        addChatMessage('assistant', 'Sorry, I couldn\'t connect to the server. Please check your connection and try again.');
    }
}

/**
 * Check if an item is a duplicate (exists in ideas or days)
 */
function isDuplicateItem(title) {
    const normalizedTitle = (title || '').toLowerCase().trim();
    if (!normalizedTitle) return false;

    // Check ideas
    if (currentTrip.ideas.some(existing => (existing.title || '').toLowerCase().trim() === normalizedTitle)) {
        return true;
    }
    // Check days
    return currentTrip.days.some(day =>
        (day.items || []).some(existing => (existing.title || '').toLowerCase().trim() === normalizedTitle)
    );
}

/**
 * Process item edits from chat (from edit_items in response).
 * Each edit has find_title plus any subset of: title, notes, category, time, location, website, day.
 * day=0 moves item to ideas pile; day>0 moves it to that day; day absent = stay in place.
 */
function processEditItems(edits) {
    if (!edits || edits.length === 0) return;

    let changedCount = 0;

    edits.forEach(edit => {
        const findTitle = (edit.find_title || '').toLowerCase().trim();
        if (!findTitle) return;

        // Find the item in ideas or days
        let foundItem = null;
        let foundIn = null; // 'ideas' or day index (number)

        const ideasMatch = currentTrip.ideas.findIndex(
            it => (it.title || '').toLowerCase().trim() === findTitle
        );
        if (ideasMatch >= 0) {
            foundItem = currentTrip.ideas[ideasMatch];
            foundIn = 'ideas';
        } else {
            outer: for (let d = 0; d < currentTrip.days.length; d++) {
                const items = currentTrip.days[d].items || [];
                for (let i = 0; i < items.length; i++) {
                    if ((items[i].title || '').toLowerCase().trim() === findTitle) {
                        foundItem = items[i];
                        foundIn = d;
                        break outer;
                    }
                }
            }
        }

        if (!foundItem) {
            console.warn('[edit_item] Item not found:', edit.find_title);
            return;
        }

        // Apply field updates (only keys explicitly present in the edit)
        if ('title' in edit) foundItem.title = edit.title;
        if ('notes' in edit) foundItem.notes = edit.notes;
        if ('category' in edit) foundItem.category = edit.category;
        if ('time' in edit) foundItem.time = edit.time || null;
        if ('location' in edit) foundItem.location = edit.location;
        if ('website' in edit) foundItem.website = edit.website;

        // Handle day/location move
        if ('day' in edit) {
            const targetDay = edit.day; // 0 = ideas pile, 1+ = day number

            // Remove from current location
            if (foundIn === 'ideas') {
                currentTrip.ideas = currentTrip.ideas.filter(it => it !== foundItem);
            } else {
                currentTrip.days[foundIn].items = currentTrip.days[foundIn].items.filter(it => it !== foundItem);
            }

            // Insert at new location
            if (!targetDay || targetDay <= 0) {
                currentTrip.ideas.push(foundItem);
            } else {
                const dayIndex = targetDay - 1;
                while (currentTrip.days.length <= dayIndex) {
                    const newDayNum = currentTrip.days.length + 1;
                    currentTrip.days.push({ day_number: newDayNum, date: null, items: [] });
                }
                if (!currentTrip.days[dayIndex].items) currentTrip.days[dayIndex].items = [];
                currentTrip.days[dayIndex].items.push(foundItem);
            }
        }

        changedCount++;
    });

    if (changedCount > 0) {
        currentTrip.days.forEach((day, index) => sortDayItemsByTime(index));
        renderDays();
        renderIdeas();
        triggerAutoSave();
    }
}

/**
 * Process items to add from chat (from add_items in response)
 */
function processAddItems(items) {
    if (!items || items.length === 0) return;

    let addedCount = 0;
    items.forEach(item => {
        // Only block duplicates on the exact same day - same event on different
        // days (e.g. Mariners Game on Jun 16, 17, 18) is intentional and fine.
        const targetDayIndex = item.day ? item.day - 1 : -1;
        if (targetDayIndex >= 0 && targetDayIndex < currentTrip.days.length) {
            const dayItems = currentTrip.days[targetDayIndex].items || [];
            const titleLower = (item.title || '').toLowerCase().trim();
            if (dayItems.some(ex => (ex.title || '').toLowerCase().trim() === titleLower)) {
                addChatMessage('assistant', `**${item.title}** is already on that day.`);
                return;
            }
        }

        const newItem = {
            title: item.title || 'Untitled',
            category: item.category || 'activity',
            location: item.location || '',
            website: item.website || null,
            notes: item.notes || '',
            time: item.time || null,
            end_time: item.end_time || null
        };

        // Check if day is specified
        if (item.day !== undefined && item.day !== null && item.day > 0) {
            const dayIndex = item.day - 1; // Convert 1-indexed to 0-indexed

            // Auto-create days if they don't exist yet
            while (currentTrip.days.length <= dayIndex) {
                const newDayNum = currentTrip.days.length + 1;
                currentTrip.days.push({
                    day_number: newDayNum,
                    date: null,
                    items: []
                });
            }

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
            addedCount++;
        } else {
            // No day specified, add to ideas pile
            currentTrip.ideas.push(newItem);
            addedCount++;
        }
    });

    // Re-render and save only if something was added
    if (addedCount > 0) {
        // Sort all days by time
        currentTrip.days.forEach((day, index) => sortDayItemsByTime(index));
        renderDays();
        renderIdeas();
        triggerAutoSave();
    }
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

    // If there are suggested items, strip out their descriptions from content
    let displayContent = content;
    if (suggestedItems && suggestedItems.length > 0) {
        // Remove paragraphs that start with any suggested item title
        suggestedItems.forEach(item => {
            if (item.title) {
                // Escape special regex characters in title
                const escapedTitle = item.title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                // Remove "Title - description" or "**Title** - description" paragraphs
                const patterns = [
                    new RegExp(`\\n\\*\\*${escapedTitle}\\*\\*[^\\n]*`, 'gi'),
                    new RegExp(`\\n${escapedTitle}\\s*[-–—:]\\s*[^\\n]*`, 'gi'),
                    new RegExp(`\\n\\d+\\.\\s*\\*\\*${escapedTitle}\\*\\*[^\\n]*`, 'gi'),
                    new RegExp(`\\n\\d+\\.\\s*${escapedTitle}[^\\n]*`, 'gi'),
                    new RegExp(`\\n[-•*]\\s*\\*\\*${escapedTitle}\\*\\*[^\\n]*`, 'gi'),
                    new RegExp(`\\n[-•*]\\s*${escapedTitle}[^\\n]*`, 'gi'),
                ];
                patterns.forEach(pattern => {
                    displayContent = displayContent.replace(pattern, '');
                });
            }
        });
        // Clean up extra newlines
        displayContent = displayContent.replace(/\n{3,}/g, '\n\n').trim();
    }
    bubble.innerHTML = formatMessageContent(displayContent);

    // Add suggested items as cards with action buttons
    if (suggestedItems && suggestedItems.length > 0) {
        const suggestionsContainer = document.createElement('div');
        suggestionsContainer.className = 'suggestions-container';

        suggestedItems.forEach((item, index) => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'suggestion-item';

            // Source badge (CURATED vs AI_PICK)
            const source = item.source || 'AI_PICK';
            const sourceBadgeClass = source === 'CURATED' ? 'curated' : 'ai-pick';
            const sourceBadgeText = source === 'CURATED' ? 'Curated' : 'AI Pick';
            const sourceBadge = `<span class="source-badge ${sourceBadgeClass}">${sourceBadgeText}</span>`;

            // Collection tag (origin)
            const collectionTag = item.collection && item.collection !== 'Saved'
                ? `<span class="collection-tag" title="${escapeHtml(item.collection)}">${escapeHtml(item.collection)}</span>`
                : '';

            const headerDiv = document.createElement('div');
            headerDiv.className = 'suggestion-item-header';
            headerDiv.innerHTML = `
                <div class="source-badges">${sourceBadge}${collectionTag}</div>
                <span class="suggestion-item-title">${escapeHtml(item.title)}</span>
            `;
            itemDiv.appendChild(headerDiv);

            // Website and Maps links row
            const linksDiv = document.createElement('div');
            linksDiv.className = 'suggestion-links';

            // Website link - use actual website or Google search
            const websiteUrl = item.website
                ? item.website
                : `https://www.google.com/search?q=${encodeURIComponent(item.title)}`;
            const websiteTitle = item.website ? 'Visit website' : 'Search on Google';
            linksDiv.innerHTML = `
                <a href="${escapeHtml(websiteUrl)}" target="_blank" class="suggestion-link" title="${websiteTitle}">
                    <i class="fas fa-globe"></i> Website
                </a>
                <a href="https://www.google.com/maps/search/${encodeURIComponent(item.title + (item.location ? ', ' + item.location : ''))}" target="_blank" class="suggestion-link" title="View on Google Maps">
                    <i class="fas fa-map-marker-alt"></i> Maps
                </a>
            `;
            itemDiv.appendChild(linksDiv);

            if (item.notes) {
                const notesDiv = document.createElement('div');
                notesDiv.className = 'suggestion-item-notes';
                notesDiv.textContent = item.notes;
                itemDiv.appendChild(notesDiv);
            }

            // Button container for multiple buttons
            const btnContainer = document.createElement('div');
            btnContainer.className = 'suggestion-buttons';

            // Add to Ideas button
            const btnIdeas = document.createElement('button');
            btnIdeas.className = 'btn-add-to-ideas';
            btnIdeas.innerHTML = '<i class="fas fa-lightbulb"></i> Ideas';
            btnIdeas.title = 'Add to Ideas pile';
            btnIdeas.addEventListener('click', () => {
                const added = addToIdeas(item);
                if (added) {
                    btnIdeas.innerHTML = '<i class="fas fa-check"></i> Added!';
                    btnIdeas.disabled = true;
                    btnIdeas.classList.add('added');
                } else {
                    btnIdeas.innerHTML = '<i class="fas fa-times"></i> Exists';
                    btnIdeas.disabled = true;
                }
            });
            btnContainer.appendChild(btnIdeas);

            // Add to Itinerary button (with day picker)
            const btnItinerary = document.createElement('button');
            btnItinerary.className = 'btn-add-to-itinerary';
            btnItinerary.innerHTML = '<i class="fas fa-calendar-plus"></i> Add to Day';
            btnItinerary.title = 'Add to a specific day';
            btnItinerary.addEventListener('click', () => {
                showDayPickerDialog(item, btnItinerary);
            });
            btnContainer.appendChild(btnItinerary);

            itemDiv.appendChild(btnContainer);
            suggestionsContainer.appendChild(itemDiv);
        });

        bubble.appendChild(suggestionsContainer);
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
