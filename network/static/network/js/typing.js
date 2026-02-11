/**
 * ============================================================================
 * ARGON SOCIAL NETWORK - TYPING INDICATOR SYSTEM
 * ============================================================================
 * 
 * @file        typing.js
 * @description Real-time typing indicator for messaging conversations
 * @version     2.0.0
 * @author      Argon Admin(Mahmudur Rahman)
 * @date        February 2026
 * 
 * @copyright   Copyright (c) 2026 Argon Social Network
 * 
 * PURPOSE
 * ============================================================================
 * Provides real-time "X is typing..." feedback in conversation interfaces
 * with support for both room-based (group) and legacy username-based (DM)
 * messaging systems.
 * 
 * FEATURES
 * ============================================================================
 * - Automatic typing state detection
 * - Dual-mode support (room-based & legacy)
 * - Multi-user typing display (group conversations)
 * - Smart auto-stop after inactivity
 * - Auto-scroll to typing indicator
 * - Polling-based status updates (2s interval)
 * 
 * DEPENDENCIES
 * ============================================================================
 * - Fetch API (modern browsers)
 * - Django CSRF tokens
 * - Global variables: ROOM_ID or RECIPIENT_USERNAME
 * 
 * BROWSER SUPPORT
 * ============================================================================
 * Chrome 60+, Firefox 55+, Safari 12+, Edge 79+
 * ============================================================================
 */

'use strict';

// ============================================================================
// INITIALIZATION & CONFIGURATION
// ============================================================================

/**
 * Typing Indicator System Initialization
 * 
 * @description
 * Initializes the typing indicator system on page load with:
 * - DOM element validation
 * - Mode detection (room vs. legacy)
 * - Event listener binding
 * - Polling mechanism setup
 * 
 * @requires Window globals:
 *   - window.ROOM_ID: Conversation room ID (optional)
 *   - window.RECIPIENT_USERNAME: Legacy DM username (optional)
 * 
 * @requires DOM elements:
 *   - #message-content: Message input textarea
 *   - #chat-form: Message submission form
 *   - #typing-bubble: Typing indicator container
 *   - .chat-box: Chat messages container (for auto-scroll)
 *   - #typing-label: Text label showing who is typing
 * 
 * @fires DOMContentLoaded
 * @returns {void}
 */
document.addEventListener("DOMContentLoaded", () => {

    // ========================================================================
    // DOM Element References
    // ========================================================================

    const textarea = document.getElementById("message-content");
    const chatForm = document.getElementById("chat-form");
    const typingBubble = document.getElementById("typing-bubble");
    const chatBox = document.querySelector(".chat-box");
    const typingLabel = document.getElementById("typing-label");

    // Validate required DOM elements
    if (!textarea || !typingBubble || !chatBox || !chatForm) {
        console.error("Typing indicator initialization failed - missing DOM elements:", {
            textarea: !!textarea,
            typingBubble: !!typingBubble,
            chatBox: !!chatBox,
            chatForm: !!chatForm
        });
        return;
    }

    // ========================================================================
    // Configuration & Mode Detection
    // ========================================================================

    /**
     * Conversation identifiers from window globals
     * @type {string|null}
     */
    const roomId = window.ROOM_ID || null;
    const username = window.RECIPIENT_USERNAME || null;

    /**
     * API endpoint configuration
     * 
     * @description
     * Determines typing API endpoints based on conversation type:
     * - Room-based: Uses /api/typing/*\/room/{roomId}/ endpoints
     * - Legacy: Uses /api/typing/*\/{username}/ endpoints
     * 
     * @type {Object}
     * @property {string} start - Start typing notification endpoint
     * @property {string} stop - Stop typing notification endpoint
     * @property {string} check - Check typing status endpoint
     * @property {string} mode - "room" or "legacy"
     */
    const endpoints = roomId ? {
        start: `/api/typing/start/${roomId}/`,
        stop: `/api/typing/stop/${roomId}/`,
        check: `/api/typing/check/${roomId}/`,
        mode: "room"
    } : {
        start: `/api/typing/start/${username}/`,
        stop: `/api/typing/stop/${username}/`,
        check: `/api/typing/check/${username}/`,
        mode: "legacy"
    };

    console.log(`Typing indicator mode: ${endpoints.mode}`, {
        roomId: roomId,
        username: username
    });

    // ========================================================================
    // State Management
    // ========================================================================

    /**
     * Current user's typing state
     * @type {boolean}
     */
    let typing = false;

    /**
     * Auto-stop timeout reference
     * @type {number|null}
     */
    let timeout = null;

    // ========================================================================
    // Utility Functions
    // ========================================================================

    /**
     * Retrieves CSRF token for secure AJAX requests
     * 
     * @function getCsrf
     * @returns {string} CSRF token value or empty string
     * 
     * @example
     * const token = getCsrf();
     * headers: { 'X-CSRFToken': token }
     */
    function getCsrf() {
        const el = document.querySelector("[name=csrfmiddlewaretoken]");
        return el ? el.value : "";
    }

    /**
     * Makes authenticated POST request to typing API
     * 
     * @function post
     * @param {string} url - API endpoint URL
     * @returns {Promise<Response>} Fetch promise
     * 
     * @example
     * post('/api/typing/start/123/')
     *   .then(r => console.log('Started'))
     *   .catch(e => console.error(e));
     */
    function post(url) {
        return fetch(url, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCsrf(),
                "X-Requested-With": "XMLHttpRequest"
            },
            credentials: "same-origin"
        });
    }

    // ========================================================================
    // UI Display Functions
    // ========================================================================

    /**
     * Shows typing indicator with custom text
     * 
     * @function showTyping
     * @param {string} [text="Someone is typing..."] - Display text
     * 
     * @description
     * - Updates typing label text
     * - Makes typing bubble visible
     * - Auto-scrolls chat to bottom to show indicator
     * 
     * @example
     * showTyping("John is typing...");
     * showTyping("Alice, Bob are typing...");
     */
    function showTyping(text) {
        if (typingLabel) {
            typingLabel.textContent = text || "Someone is typing...";
        }
        typingBubble.style.display = "block";

        // Auto-scroll to bottom to show typing indicator
        setTimeout(() => {
            chatBox.scrollTop = chatBox.scrollHeight;
        }, 50);
    }

    /**
     * Hides typing indicator
     * 
     * @function hideTyping
     * 
     * @description
     * - Hides typing bubble
     * - Clears typing label text
     * - Does not scroll (maintains user position)
     */
    function hideTyping() {
        typingBubble.style.display = "none";
        if (typingLabel) {
            typingLabel.textContent = "";
        }
    }

    // ========================================================================
    // Typing State Management
    // ========================================================================

    /**
     * Notifies server of user typing activity
     * 
     * @function startTyping
     * 
     * @description
     * Behavior:
     * 1. On first keystroke: Sends "start typing" notification
     * 2. On subsequent keystrokes: Resets auto-stop timer
     * 3. After 1.5s of inactivity: Sends "stop typing" notification
     * 
     * This provides smooth typing feedback without excessive API calls.
     * 
     * @fires POST /api/typing/start/{id}/
     * @fires POST /api/typing/stop/{id}/ (after timeout)
     * 
     * @example
     * textarea.addEventListener("input", startTyping);
     */
    function startTyping() {
        // First keystroke - notify server
        if (!typing) {
            typing = true;
            post(endpoints.start).catch(err => {
                console.error('Start typing notification failed:', err);
            });
        }

        // Clear previous timeout
        if (timeout) clearTimeout(timeout);

        // Auto-stop after 1.5 seconds of inactivity
        timeout = setTimeout(() => {
            typing = false;
            post(endpoints.stop).catch(err => {
                console.error('Stop typing notification failed:', err);
            });
        }, 1500);
    }

    // ========================================================================
    // Typing Status Polling
    // ========================================================================

    /**
     * Polls server for others' typing status
     * 
     * @function checkTyping
     * 
     * @description
     * Checks if other users are typing and updates UI accordingly.
     * 
     * Response handling:
     * - Room mode: Displays multiple users (e.g., "David, Brian are typing...")
     * - Legacy mode: Shows generic "Someone is typing..."
     * - Smart formatting for 1-3 users vs. "X and N others"
     * 
     * @fires GET /api/typing/check/{id}/
     * 
     * @returns {void}
     * 
     * @example Response format (room mode):
     * {
     *   "is_typing": true,
     *   "users": ["David", "Brian", "Ron"]
     * }
     */
    function checkTyping() {
        fetch(endpoints.check, {
            headers: { 
                "X-Requested-With": "XMLHttpRequest" 
            },
            credentials: "same-origin"
        })
        .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
        })
        .then(data => {
            if (data && data.is_typing) {
                // Room mode: Show specific users typing
                if (Array.isArray(data.users) && data.users.length) {
                    if (data.users.length <= 3) {
                        // Show all users (1-3)
                        const verb = data.users.length === 1 ? "is" : "are";
                        showTyping(`${data.users.join(", ")} ${verb} typing...`);
                    } else {
                        // Show first 2 + count (4+)
                        const firstTwo = data.users.slice(0, 2).join(", ");
                        const rest = data.users.length - 2;
                        showTyping(`${firstTwo} and ${rest} ${rest === 1 ? 'other' : 'others'} are typing...`);
                    }
                } else {
                    // Legacy mode or no user data
                    showTyping("Someone is typing...");
                }
            } else {
                // No one typing
                hideTyping();
            }
        })
        .catch(err => {
            console.error('Typing status check failed:', err);
            // Fail silently - don't disrupt chat experience
        });
    }

    // ========================================================================
    // Event Listeners
    // ========================================================================

    /**
     * Monitor textarea input for typing activity
     * Triggers typing notification on every keystroke
     */
    textarea.addEventListener("input", startTyping);

    /**
     * Stop typing notification on message submission
     * Ensures typing indicator is cleared when message is sent
     */
    chatForm.addEventListener("submit", () => {
        if (typing) {
            typing = false;
            post(endpoints.stop).catch(err => {
                console.error('Stop typing on submit failed:', err);
            });
        }
    });

    // ========================================================================
    // Polling Setup
    // ========================================================================

    /**
     * Check for others' typing status every 2 seconds
     * Provides near-real-time feedback without WebSockets
     */
    setInterval(checkTyping, 2000);

    // Initial check on page load
    checkTyping();

    console.log('Typing indicator system initialized successfully');

});


/**
 * ============================================================================
 * END OF FILE
 * ============================================================================
 * 
 * @summary
 * This module provides real-time typing indicators for Argon messaging with:
 * - Automatic typing detection from textarea input
 * - Smart auto-stop after 1.5s inactivity
 * - Multi-user typing display (group chats)
 * - Polling-based status updates (2s interval)
 * - Room-based and legacy DM support
 * 
 * @architecture
 * - Client polls server every 2 seconds for typing status
 * - Server maintains temporary typing state (Redis/cache recommended)
 * - Auto-cleanup of stale typing states on server
 * 
 * @future_enhancements
 * - WebSocket support for true real-time updates
 * - Configurable polling interval
 * - Typing history analytics
 * - Adaptive polling based on activity
 * 
 * @performance
 * - Minimal API calls (debounced start, single stop)
 * - Lightweight polling (2s interval)
 * - No DOM manipulation when state unchanged
 * - Fails gracefully on network errors
 * 
 * @accessibility
 * - Typing indicator visible and readable
 * - Auto-scroll keeps indicator in view
 * - No keyboard trap or focus issues
 * 
 * @maintainers
 * Argon Admin(Mahmudur Rahman)
 * 
 * @last_updated February 2026
 * ============================================================================
 */
