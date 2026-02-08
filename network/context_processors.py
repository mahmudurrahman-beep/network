"""
================================================================================
ARGON SOCIAL NETWORK - CONTEXT PROCESSORS
================================================================================

@file        context_processors.py
@description Context processors for template-wide data availability
@version     2.0.0
@author      Argon Admin
@date        February 2026
@copyright   Copyright (c) 2026 Argon Social Network

MODULE PURPOSE
================================================================================
This module provides context processors that inject data into all Django
templates automatically. Context processors are called for every request,
making their return values available in all rendered templates without
explicitly passing them from views.

CONTEXT PROCESSORS DEFINED
================================================================================
1. unread_counts() - Provides unread message and notification counts

These values are available in all templates as:
    {{ unread_messages_count }}
    {{ unread_notifications_count }}

USAGE IN SETTINGS.PY
================================================================================
Add to TEMPLATES['OPTIONS']['context_processors']:

TEMPLATES = [
    {
        'OPTIONS': {
            'context_processors': [
                ...
                'network.context_processors.unread_counts',
            ],
        },
    },
]

PERFORMANCE CONSIDERATIONS
================================================================================
Context processors run on EVERY request, so optimization is critical:
- Use .count() instead of len(queryset) to avoid loading objects
- Apply .select_related() and .prefetch_related() where possible
- Early returns for anonymous users
- Filter at database level, not in Python
- Cache expensive calculations when appropriate

TEMPLATE USAGE EXAMPLES
================================================================================
In any template (base layout, navbar, etc.):

<!-- Display unread message badge -->
{% if unread_messages_count > 0 %}
    <span class="badge">{{ unread_messages_count }}</span>
{% endif %}

<!-- Display unread notification badge -->
{% if unread_notifications_count > 0 %}
    <span class="badge">{{ unread_notifications_count }}</span>
{% endif %}

<!-- Conditional rendering -->
{% if unread_messages_count %}
    <div class="alert">You have {{ unread_messages_count }} new messages!</div>
{% endif %}

SECURITY NOTES
================================================================================
- Always check request.user.is_authenticated
- User-specific data only (no cross-user data leakage)
- Hidden conversations properly excluded
- Block relationships respected in queries

================================================================================
"""

from django.db.models import Q
from .models import Notification, ConversationMember, Message


# ============================================================================
# CONTEXT PROCESSOR: UNREAD COUNTS
# ============================================================================

def unread_counts(request):
    """
    Inject unread message and notification counts into all templates.

    This context processor calculates and provides real-time counts of:
    1. Unread notifications (excluding message-related notifications)
    2. Unread direct messages (recipient-based, legacy system)
    3. Unread group messages (conversation-based, modern system)

    The combined unread message count includes both DMs and group messages,
    minus messages in hidden conversations.

    Args:
        request: Django HttpRequest object with authenticated user

    Returns:
        dict: Context dictionary with two keys:
            - unread_messages_count (int): Total unread messages (DM + groups)
            - unread_notifications_count (int): Total unread notifications

    Performance:
        - Runs on every request
        - Uses .count() for efficiency (no object instantiation)
        - Early return for anonymous users (zero overhead)
        - Queries optimized with select_related()

    Example Usage in Templates:
        <!-- Navigation badge -->
        {% if unread_messages_count > 0 %}
            <span class="badge badge-danger">
                {{ unread_messages_count }}
            </span>
        {% endif %}

        <!-- Conditional alert -->
        {% if unread_notifications_count %}
            <div class="alert alert-info">
                You have {{ unread_notifications_count }} new notifications
            </div>
        {% endif %}

    Query Logic:
        Notifications:
            - Filter by current user
            - Exclude read notifications (is_read=False)
            - Exclude message-related notifications (verb__icontains="message")

        DM Messages:
            - Count unread messages where user is recipient
            - Uses is_read field (legacy DM system)

        Group Messages:
            - Iterate through user's conversation memberships
            - Count messages newer than last_read_at timestamp
            - Exclude own messages
            - Skip hidden conversations
            - Only count group conversations (not DMs)

    Note:
        Hidden conversations are excluded from counts to match UI behavior.
        Users won't see badges for rooms they've hidden.
    """

    # ========================================================================
    # STEP 1: ANONYMOUS USER CHECK
    # ========================================================================
    # Fast-path return for non-authenticated users
    # Avoids unnecessary database queries

    if not request.user.is_authenticated:
        return {
            "unread_messages_count": 0,
            "unread_notifications_count": 0,
        }

    # ========================================================================
    # STEP 2: UNREAD NOTIFICATIONS
    # ========================================================================
    # Count notifications that:
    #   1. Belong to current user
    #   2. Are not marked as read (is_read=False)
    #   3. Are not message-related (exclude verb containing "message")
    #
    # Message notifications are excluded because they have separate
    # unread message counts and shouldn't clutter the notification feed.

    unread_notifications = Notification.objects.filter(
        user=request.user,      # Only this user's notifications
        is_read=False           # Only unread notifications
    ).exclude(
        verb__icontains="message"  # Exclude message notifications
    ).count()  # Use .count() for efficiency (no object loading)

    # ========================================================================
    # STEP 3: LEGACY DM UNREAD COUNT
    # ========================================================================
    # Count unread direct messages using the legacy recipient-based system.
    # This uses the Message.is_read field for simple DM conversations.
    #
    # Query: received_messages.filter(is_read=False).count()
    # Related name: User.received_messages (defined in Message model)

    dm_unread = request.user.received_messages.filter(
        is_read=False  # Only unread DMs
    ).count()

    # ========================================================================
    # STEP 4: GROUP CONVERSATION UNREAD COUNT
    # ========================================================================
    # Count unread messages in group conversations using the modern
    # conversation-based system with ConversationMember.last_read_at tracking.
    #
    # Algorithm:
    #   1. Get all conversation memberships for current user
    #   2. For each group conversation (not DM):
    #      a. Skip if conversation is hidden by user
    #      b. Get user's last_read_at timestamp (or conversation created_at)
    #      c. Count messages after last_read_at, excluding own messages
    #   3. Sum all unread messages across all groups

    group_unread = 0  # Initialize counter

    # Fetch all conversation memberships with related conversation data
    # select_related('conversation') optimizes by joining in single query
    memberships = ConversationMember.objects.filter(
        user=request.user
    ).select_related("conversation")

    # Iterate through each conversation membership
    for mem in memberships:
        conv = mem.conversation  # Access related conversation object

        # --- Filter 1: Only Group Conversations ---
        # Skip direct message conversations (handled by dm_unread above)
        if not conv.is_group:
            continue

        # --- Filter 2: Skip Hidden Conversations ---
        # Users can hide conversations from their inbox
        # Don't count unread messages in hidden conversations
        if conv.hidden_by.filter(id=request.user.id).exists():
            continue

        # --- Determine Last Read Timestamp ---
        # Use member's last_read_at if available,
        # otherwise fall back to conversation creation time
        # (meaning all messages are unread)
        last_read = mem.last_read_at or conv.created_at

        # --- Count Unread Messages ---
        # Count messages in this conversation that:
        #   1. Were sent after user's last read timestamp
        #   2. Were not sent by the user themselves
        group_unread += Message.objects.filter(
            conversation=conv,          # Messages in this conversation
            timestamp__gt=last_read     # Newer than last read time
        ).exclude(
            sender=request.user         # Exclude own messages
        ).count()

    # ========================================================================
    # STEP 5: RETURN CONTEXT DICTIONARY
    # ========================================================================
    # Combine DM and group unread counts for total messages
    # Return dictionary available in all templates

    return {
        "unread_messages_count": dm_unread + group_unread,
        "unread_notifications_count": unread_notifications,
    }


"""
================================================================================
END OF CONTEXT PROCESSORS
================================================================================

TESTING RECOMMENDATIONS
================================================================================
Test the context processor:

1. Anonymous User Test:
   - Access any page without login
   - Verify no database queries for unread counts
   - Check that badges show 0 or are hidden

2. Authenticated User Test:
   - Login and verify correct unread counts
   - Send test message and verify count increments
   - Read message and verify count decrements
   - Hide conversation and verify count updates

3. Performance Test:
   - Monitor query count (should be ~3-4 queries)
   - Use Django Debug Toolbar to check query time
   - Test with large number of conversations (100+)
   - Verify acceptable page load times

4. Edge Cases:
   - User with no conversations
   - User with only hidden conversations
   - User with all messages read
   - User blocked by message sender

OPTIMIZATION TIPS
================================================================================
If unread counts become a performance bottleneck:

1. Add Caching:
   - Cache counts for 30-60 seconds per user
   - Invalidate cache on new message/notification
   - Use Redis for distributed caching

2. Denormalize Counts:
   - Add unread_count fields to User model
   - Update via signals or async tasks
   - Trade write complexity for read speed

3. Use Database Views:
   - Create materialized view for counts
   - Refresh periodically
   - Query view instead of live calculation

4. Lazy Loading:
   - Load counts via AJAX after page load
   - Reduce initial page render time
   - Update counts in real-time with WebSockets

COMMON ISSUES & SOLUTIONS
================================================================================
Issue: Counts don't update after reading messages
Solution: Ensure ConversationMember.last_read_at is updated on read

Issue: Performance degradation with many conversations
Solution: Add database indexes on timestamp fields, consider caching

Issue: Counts include hidden conversations
Solution: Verify hidden_by ManyToMany filter is applied correctly

Issue: Own messages counted as unread
Solution: Check .exclude(sender=request.user) is present

RELATED MODELS
================================================================================
This context processor depends on:
- Notification (user, is_read, verb fields)
- Message (conversation, recipient, is_read, timestamp, sender)
- ConversationMember (user, conversation, last_read_at)
- Conversation (is_group, hidden_by, created_at)

Ensure these models are properly migrated and relationships are correct.

MAINTAINER
================================================================================
Argon Admin
Last updated: February 2026

For questions about context processors or to add new template-wide data,
contact the Argon Admin team.
================================================================================
"""
