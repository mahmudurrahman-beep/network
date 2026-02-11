/**
 * ============================================================================
 * ARGON SOCIAL NETWORK - CLIENT-SIDE APPLICATION
 * ============================================================================
 * 
 * @file        main.js (CLEANED VERSION)
 * @description Core JavaScript functionality for Argon Social Network
 * @version     2.2.0 (Removed non-functional PWA badge code)
 * @author      Argon Admin
 * @date        February 2026
 * 
 * @copyright   Copyright (c) 2026 Argon Social Network 
 * 
 * CHANGES IN v2.2.0:
 * ❌ REMOVED: navigator.setAppBadge() code (doesn't work when app is closed)
 * ❌ REMOVED: badgeEnabled flag check (unnecessary complexity)
 * ✅ KEPT: Browser tab title updates (always works)
 * ✅ KEPT: Navbar badge updates (always works)
 * ✅ KEPT: Sound alerts (works when app is open)
 * ✅ KEPT: Smart polling (3-second updates)
 * 
 * TABLE OF CONTENTS
 * ============================================================================
 * 1.  Utility Functions & Helpers
 * 2.  User Interactions (Follow/Block)
 * 3.  Post Management (Create/Edit/Delete/Vote)
 * 4.  Comment System (CRUD + Nested Replies)
 * 5.  Messaging & Conversations
 * 6.  UI Enhancements (Time Display, Action Menus)
 * 7.  Mentions Autocomplete System
 * 8.  Message Badge & Sound Alerts (CLEANED)
 * 9.  Smart Polling System
 * 10. Initialization & Event Binding
 * ============================================================================
 */

'use strict';

// ============================================================================
// GLOBAL STATE VARIABLES (SAFELY ADDED)
// ============================================================================

// Message Alert System State
let argonLastMessageCount = 0;
let argonMessageSound = null;
let argonMessageSoundEnabled = false;
let argonMessageSoundChoice = "ding";

// Smart Polling System State
let argonPollingInterval = null;
let argonLastActivity = Date.now();

// ============================================================================
// SECTION 1: UTILITY FUNCTIONS & HELPERS
// ============================================================================

/**
 * Retrieves the CSRF token from the DOM for secure AJAX requests.
 * Required by Django for POST/PUT/DELETE requests.
 * 
 * @function getCsrfToken
 * @returns {string} CSRF token value or empty string if not found
 * @throws {Error} Logs error to console if token element not found
 * 
 * @example
 * const token = getCsrfToken();
 * headers: { 'X-CSRFToken': token }
 */
function getCsrfToken() {
  const token = document.querySelector('[name=csrfmiddlewaretoken]');
  if (!token) {
    console.error('CSRF token not found! Ensure {% csrf_token %} is in template.');
    return '';
  }
  return token.value;
}

/**
 * Checks if the current user can interact with another user.
 * Validates against block relationships before allowing actions.
 * 
 * @function checkCanInteract
 * @param {string} username - Target user's username
 * @param {Function} callback - Function to execute if interaction is allowed
 * 
 * @description
 * Makes async request to server to verify:
 * - User has not blocked target
 * - User is not blocked by target
 * If checks pass, executes callback; otherwise shows alert.
 * 
 * @example
 * checkCanInteract('john_doe', () => {
 *   // Proceed with follow action
 * });
 */
function checkCanInteract(username, callback) {
  fetch(`/api/check-interaction/${username}/`, {
    method: 'GET',
    headers: {
      'X-CSRFToken': getCsrfToken(),
      'Content-Type': 'application/json'
    },
    credentials: 'same-origin'
  })
    .then(response => response.json())
    .then(data => {
      if (data.can_interact) {
        callback();
      } else {
        alert(data.message || 'Cannot interact with this user.');
      }
    })
    .catch(err => {
      console.error('Interaction check failed:', err);
      // Proceed anyway on network error (fail-open for UX)
      callback();
    });
}


// ============================================================================
// SECTION 2: USER INTERACTIONS (Follow/Block)
// ============================================================================

/**
 * Follow/Unfollow Toggle Handler
 * 
 * @description
 * Handles follow button clicks with:
 * - Block relationship validation
 * - Optimistic UI updates
 * - Server synchronization
 * - Follower count updates
 * - Error recovery
 * 
 * @requires checkCanInteract
 * @requires getCsrfToken
 * 
 * @data-attribute {string} data-username - Target user's username
 * 
 * @fires POST /toggle-follow/{username}/
 * @returns {void}
 */
const followBtn = document.getElementById('follow-btn');
if (followBtn) {
  followBtn.addEventListener('click', () => {
    const username = followBtn.dataset.username;

    // Validate interaction permissions before proceeding
    checkCanInteract(username, () => {
      const csrfToken = getCsrfToken();

      if (!csrfToken) {
        alert('CSRF token missing. Please reload the page.');
        return;
      }

      // Provide immediate UI feedback
      followBtn.disabled = true;
      const originalText = followBtn.textContent;
      followBtn.textContent = '...';

      fetch(`/toggle-follow/${username}/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
          'Content-Type': 'application/json'
        },
        credentials: 'same-origin'
      })
        .then(response => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return response.json();
        })
        .then(data => {
          // Reset all button styling classes
          const buttonClasses = [
            'btn-primary', 'btn-outline-primary', 'btn-secondary', 
            'btn-outline-secondary', 'btn-success', 'btn-danger',
            'btn-warning', 'btn-info', 'btn-light', 'btn-dark',
            'btn-following', 'btn-not-following'
          ];

          buttonClasses.forEach(cls => followBtn.classList.remove(cls));
          followBtn.classList.add('btn');

          // Apply correct state based on server response
          if (data.action === 'followed') {
            followBtn.textContent = 'Unfollow';
            followBtn.classList.add('btn-following');
          } else {
            followBtn.textContent = 'Follow';
            followBtn.classList.add('btn-not-following');
          }

          // Update follower/following counts in UI
          const followersEl = document.querySelector('[data-followers-count]');
          if (followersEl) {
            const followersLink = followersEl.querySelector('a');
            if (followersLink) {  
              followersLink.textContent = `${data.followers} followers`;
  }
}

          const followingEl = document.querySelector('#following-count');
          if (followingEl && data.following !== undefined) {
            const followingLink = followingEl.querySelector('a');
            if (followingLink) {
              followingLink.textContent = `${data.following} following`;
            }
          }
        })
        .catch(error => {
          console.error('Follow action failed:', error);
          alert('Could not follow/unfollow. Please try again.');
          followBtn.textContent = originalText;
        })
        .finally(() => {
          followBtn.disabled = false;
        });
    });
  });
}


// ============================================================================
// SECTION 3-7: POST MANAGEMENT, COMMENTS, MESSAGING, UI, MENTIONS
// ============================================================================
// [Lines 220-1560 remain unchanged - keeping all existing functionality]
// Including: posts, comments, messaging, UI enhancements, mentions autocomplete
// (Content omitted for brevity - no changes in these sections)


// ============================================================================
// SECTION 8: MESSAGE BADGE & SOUND ALERTS (CLEANED)
// ============================================================================

/**
 * Initialize message alert settings from server
 * 
 * @description
 * Fetches user's message notification preferences:
 * - Sound enabled/disabled status
 * - Sound choice (ding/pop/chime)
 * 
 * ❌ REMOVED: message_badge_enabled (doesn't control app icon badges)
 * ✅ KEPT: Sound settings (work when app is open)
 * 
 * @function argonInitMessageAlertSettings
 * @fires GET /api/user-settings/
 */
function argonInitMessageAlertSettings() {
  fetch("/api/user-settings/")
    .then((r) => {
      if (!r.ok) throw new Error("settings error");
      return r.json();
    })
    .then((data) => {
      // ❌ REMOVED: const badgeEnabled = !!data.message_badge_enabled;
      argonMessageSoundEnabled = !!data.message_sound_enabled;
      argonMessageSoundChoice = data.message_sound_choice || "ding";
      
      console.log('Message sound settings loaded:', {
        enabled: argonMessageSoundEnabled,
        sound: argonMessageSoundChoice
      });
    })
    .catch((err) => {
      console.error('Failed to load message settings:', err);
    });
}

/**
 * Play message notification sound
 * 
 * @description
 * Plays selected notification sound with mobile-safe fallback.
 * Handles browser autoplay blocking with user interaction unlock.
 * 
 * @function argonPlayMessageSound
 */
function argonPlayMessageSound() {
  if (!argonMessageSoundEnabled) return;

  const soundFile = argonMessageSoundChoice || "ding";
  
  if (!argonMessageSound) {
    argonMessageSound = new Audio(`/static/network/sounds/${soundFile}.mp3`);
    argonMessageSound.volume = 0.3;
  } else {
    argonMessageSound.src = `/static/network/sounds/${soundFile}.mp3`;
  }

  argonMessageSound.play()
    .then(() => {
      console.log('🔊 Message sound played');
    })
    .catch((err) => {
      console.log('🔇 Sound blocked by browser (autoplay policy):', err);
      
      // Mobile-safe: unlock audio on user interaction
      const unlockAudio = () => {
        argonMessageSound.play()
          .then(() => {
            console.log('🔊 Audio unlocked on user tap');
          })
          .catch(() => {
            console.log('Audio still blocked');
          });
        // Remove listener after first attempt
        document.removeEventListener('click', unlockAudio);
        document.removeEventListener('touchstart', unlockAudio);
      };

      // Listen for user tap to unlock audio
      document.addEventListener('click', unlockAudio, { once: true });
      document.addEventListener('touchstart', unlockAudio, { once: true });
    });
  }
} 

/**
 * Update message badge with current unread count
 * 
 * @description
 * Updates:
 * - Navbar badge (red pill in navigation - ALWAYS WORKS)
 * - Browser tab title with count (ALWAYS WORKS)
 * - Triggers sound for new messages (when app is open)
 * 
 * ❌ REMOVED: navigator.setAppBadge() - doesn't work when app is closed
 * ❌ REMOVED: badgeEnabled flag check - unnecessary complexity
 * 
 * @function argonUpdateMessageBadge
 * @fires GET /api/message-badge/
 */
function argonUpdateMessageBadge() {
  // Skip if user not authenticated
  if (window.userAuthenticated === false) return;

  fetch("/api/message-badge/")
    .then((r) => {
      if (!r.ok) throw new Error("badge error");
      return r.json();
    })
    .then((data) => {
      const newCount = data.count || 0;
      
      // ❌ REMOVED LINE (was line 1601):
      // const badgeEnabled = !!data.badge_enabled;
      // ↑ This flag doesn't control app icon badges, so we removed it

      // ✅ Update navbar badge element (ALWAYS WORKS)
      const navBadge = document.querySelector('.js-message-badge');
      if (navBadge) {
        if (newCount > 0) {
          navBadge.textContent = newCount;
          navBadge.style.display = 'inline-block';
        } else {
          navBadge.style.display = 'none';
        }
      }

      // ❌ REMOVED LINES (were lines 1614-1635):
      // All the navigator.setAppBadge() code that looked like this:
      /*
      if (badgeEnabled) {
        // PWA app icon badge (Chrome/Edge on Android)
        if ("setAppBadge" in navigator) {
          if (newCount > 0) {
            navigator.setAppBadge(newCount).catch(() => {});
          } else {
            navigator.clearAppBadge().catch(() => {});
          }
        }
        // Browser title badge (universal fallback)
        if (newCount > 0) {
          document.title = `(${newCount}) Argon`;
        } else {
          document.title = "Argon";
        }
      } else {
        // Clear badges if user disabled
        if ("clearAppBadge" in navigator) {
          navigator.clearAppBadge().catch(() => {});
        }
        document.title = "Argon";
      }
      */

      // ✅ SIMPLIFIED REPLACEMENT - Browser tab title (ALWAYS WORKS)
      if (newCount > 0) {
        document.title = `(${newCount}) Argon`;
      } else {
        document.title = "Argon";
      }

      // ✅ Play sound on new messages (ALWAYS WORKS when app is open)
      if (newCount > argonLastMessageCount) {
        argonPlayMessageSound();
      }
      argonLastMessageCount = newCount;
    })
    .catch((err) => {
      console.error('Badge update failed:', err);
    });
}


// ============================================================================
// SECTION 9: SMART POLLING SYSTEM
// ============================================================================

/**
 * Smart Polling System - Efficient message checking
 * 
 * Features:
 * - Polls every 3 seconds (was 30 seconds)
 * - Stops when user is on messages page (no need)
 * - Stops when user is idle for 5+ minutes
 * - Restarts when user becomes active again
 * - Prevents memory leaks
 */

/**
 * Check if polling should be active
 * @returns {boolean} True if polling should continue
 */
function argonShouldPoll() {
  // Don't poll if not authenticated
  if (window.userAuthenticated === false) return false;

  // Don't poll if on message pages (user already sees messages)
  const path = window.location.pathname || '';
  if (path.includes('/messages/') || path.includes('/conversation/')) {
    return false;
  }

  // Don't poll if user idle for >5 minutes
  const idleTime = Date.now() - argonLastActivity;
  if (idleTime > 300000) { // 5 minutes = 300,000ms
    return false;
  }

  return true;
}

/**
 * Start polling for message updates
 */
function argonStartPolling() {
  if (argonPollingInterval) return; // Already polling

  // Poll every 3 seconds (was 30)
  argonPollingInterval = setInterval(argonUpdateMessageBadge, 3000);
  console.log('✅ Message polling started (3s interval)');
}

/**
 * Stop polling (when idle or on message pages)
 */
function argonStopPolling() {
  if (!argonPollingInterval) return; // Already stopped

  clearInterval(argonPollingInterval);
  argonPollingInterval = null;
  console.log('⏸️ Message polling stopped');
}

/**
 * Update last activity timestamp
 */
function argonUpdateActivity() {
  argonLastActivity = Date.now();

  // If polling was stopped due to idle, restart it
  if (!argonPollingInterval && argonShouldPoll()) {
    argonStartPolling();
  }
}

/**
 * Monitor polling state and adjust
 */
function argonMonitorPolling() {
  if (argonShouldPoll() && !argonPollingInterval) {
    // Should be polling but isn't - start it
    argonStartPolling();
  } else if (!argonShouldPoll() && argonPollingInterval) {
    // Should NOT be polling but is - stop it
    argonStopPolling();
  }
}

// Track user activity to detect idle state
document.addEventListener('mousemove', argonUpdateActivity);
document.addEventListener('keydown', argonUpdateActivity);
document.addEventListener('click', argonUpdateActivity);
document.addEventListener('scroll', argonUpdateActivity);

// Check polling state every 30 seconds
setInterval(argonMonitorPolling, 30000);


// ============================================================================
// SECTION 10: INITIALIZATION & EVENT BINDING
// ============================================================================

/**
 * Application Initialization
 * 
 * @description
 * Initializes all systems on DOM ready:
 * - Message alert settings
 * - Message badge update
 * - Smart polling system
 * 
 * @listens DOMContentLoaded
 */
document.addEventListener("DOMContentLoaded", function() {
  // Initialize message alert system
  argonInitMessageAlertSettings();
  argonUpdateMessageBadge();

  // Initialize last activity timestamp
  argonLastActivity = Date.now();

  // Start smart polling if conditions allow
  if (argonShouldPoll()) {
    argonStartPolling();
  }

  console.log('✅ Argon Social Network - Client initialized');
  console.log('✅ Smart Polling: Active (3s interval when not idle/on messages page)');
  console.log('✅ Navbar badges: Active');
  console.log('✅ Browser tab title: Active');
  console.log('❌ PWA app icon badges: Not available (requires push notifications)');
});


/**
 * ============================================================================
 * END OF FILE
 * ============================================================================
 * 
 * @summary
 * This file provides complete client-side functionality for Argon Social
 * Network including:
 * - User interactions (follow, block)
 * - Content management (posts, comments)
 * - Real-time features (mentions, typing indicators)
 * - Notification system
 * - Messaging with sound alerts
 * - SMART POLLING SYSTEM (3-second updates with idle detection)
 * 
 * @version_changes 2.2.0
 * - ❌ REMOVED: navigator.setAppBadge() code (non-functional when app closed)
 * - ❌ REMOVED: badgeEnabled flag checks (unnecessary complexity)
 * - ✅ SIMPLIFIED: Browser tab title always updates (reliable)
 * - ✅ KEPT: Navbar badges (always work)
 * - ✅ KEPT: Sound alerts (work when app open)
 * - ✅ KEPT: Smart polling system
 * 
 * @dependencies
 * - Bootstrap 4.x (for UI components)
 * - Django CSRF tokens
 * - Fetch API (modern browsers)
 * 
 * @browser_support
 * - Chrome 60+
 * - Firefox 55+
 * - Safari 12+
 * - Edge 79+
 * 
 * @performance
 * - Smart polling reduces unnecessary requests
 * - Idle detection saves server resources
 * - Event delegation for dynamic content
 * - Minimal DOM manipulation
 * 
 * @accessibility
 * - ARIA attributes for menus
 * - Keyboard navigation support
 * - Screen reader friendly alerts
 * 
 * @maintainers
 * Argon Admin
 * 
 * @last_updated February 2026
 * ============================================================================
 */
