"""
================================================================================
ARGON NETWORK - URL CONFIGURATION
================================================================================

@file        urls.py
@description Complete URL routing configuration for Argon Network
@version     2.0.0
@author      Argon Admin(Mahmudur Rahman)
@date        February 2026
@copyright   Copyright (c) 2026 Argon Network

MODULE PURPOSE
================================================================================
This module defines all URL patterns for the Argon Network application,
mapping URLs to their corresponding view functions. URLs are organized into
logical sections for maintainability and clarity.

URL STRUCTURE OVERVIEW
================================================================================
1. Core Pages & Authentication (/, login, register, activate)
2. User Profiles & Discovery (profile, edit, followers, following)
3. Posts & Content (CRUD operations, voting, detail view)
4. Comments System (add, edit, delete with nesting support)
5. Social Actions (follow, block, unblock)
6. Notifications (view, mark read, clear, delete)
7. Messaging System (inbox, conversations, rooms)
8. Group Management (create, members, admins, settings)
9. Typing Indicators (room-based and legacy DM)
10. API Endpoints (search, mentions, badges, settings)
11. Media & GIF Integration (uploads, Tenor search)
12. Password Reset Flow (Django auth views)
13. Development Media Serving (DEBUG mode only)

NAMING CONVENTIONS
================================================================================
URL names use underscore_case for consistency:
- Resource actions: <resource>_<action> (e.g., 'edit_post', 'delete_comment')
- API endpoints: Prefixed with API in URL path (e.g., '/api/mentions/')
- Conversation rooms: Use 'room' for new system, 'conversation' for legacy
- Toggles: Prefixed with 'toggle_' (e.g., 'toggle_follow', 'toggle_vote')

URL PARAMETER TYPES
================================================================================
- <str:username>: Username string (alphanumeric + underscore)
- <int:post_id>: Post primary key integer
- <int:conversation_id>: Conversation/Room primary key
- <int:user_id>: User primary key
- <int:comment_id>: Comment primary key
- <int:notification_id>: Notification primary key
- <str:token>: Activation token string
- <uidb64>/<token>: Password reset tokens (Django auth)

VIEW FUNCTION MAPPING
================================================================================
All views are imported from the 'views' module in the same package.
Password reset views use Django's built-in auth_views.

SECURITY CONSIDERATIONS
================================================================================
- All state-changing views require @login_required decorator
- CSRF protection enabled on all POST/PUT/DELETE operations
- User permissions checked in view functions
- Block relationships verified before interactions
- Admin-only actions protected in group management

PERFORMANCE NOTES
================================================================================
- Static URL patterns compiled at startup
- No regex patterns for simple integer/string parameters
- Media serving disabled in production (served by web server)

TESTING
================================================================================
To test URL resolution:
    from django.urls import reverse
    url = reverse('post_detail', kwargs={'post_id': 1})
    # Returns: '/post/1/'

================================================================================
"""

from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from . import views


# ============================================================================
# URL PATTERNS DEFINITION
# ============================================================================

urlpatterns = [

    # ========================================================================
    # SECTION 1: CORE PAGES & AUTHENTICATION
    # ========================================================================
    # Home page, user authentication, and account activation

    path(
        "", 
        views.index, 
        name="index"
    ),  # Homepage / main feed

    path(
        "login", 
        views.login_view, 
        name="login"
    ),  # User login form

    path(
        "logout", 
        views.logout_view, 
        name="logout"
    ),  # User logout action

    path(
        "register", 
        views.register, 
        name="register"
    ),  # New user registration

    path(
        "activate/<str:token>/", 
        views.activate, 
        name="activate"
    ),  # Email verification link


    # ========================================================================
    # SECTION 2: USER PROFILES & DISCOVERY
    # ========================================================================
    # Profile viewing, editing, and user discovery

    path(
        "profile/<str:username>", 
        views.profile, 
        name="profile"
    ),  # View user profile with posts

    path(
        "edit-profile/", 
        views.edit_profile, 
        name="edit_profile"
    ),  # Edit own profile (authenticated)

    path(
        "quick-upload-picture/", 
        views.quick_upload_picture, 
        name="quick_upload_picture"
    ),  # AJAX profile picture upload

    path(
        "discover/", 
        views.discover_users, 
        name="discover_users"
    ),  # Discover new users page

    path(
        "followers/<str:username>/", 
        views.followers_list, 
        name="followers_list"
    ),  # User's followers list

    path(
        "following/<str:username>/", 
        views.following_list, 
        name="following_list"
    ),  # User's following list


    # ========================================================================
    # SECTION 3: POSTS & CONTENT MANAGEMENT
    # ========================================================================
    # Post creation, viewing, editing, and voting

    path(
        "posts", 
        views.all_posts, 
        name="all_posts"
    ),  # All posts feed (public)

    path(
        "following", 
        views.following, 
        name="following"
    ),  # Following users feed (filtered)

    path(
        "post/<int:post_id>/", 
        views.post_detail, 
        name="post_detail"
    ),  # Single post detail view
    
    path(
        "new-post", 
        views.new_post, 
        name="new_post"
    ),  # Create new post (authenticated)

    path(
        "new-post/", 
        views.new_post, 
        name="new_post"
    ),  # Duplicate for trailing slash compatibility
    
    path(
        "edit-post/<int:post_id>/", 
        views.edit_post, 
        name="edit_post"
    ),  # Edit own post (PUT)

    path(
        "delete-post/<int:post_id>/", 
        views.delete_post, 
        name="delete_post"
    ),  # Delete own post (POST)

    path(
        "vote/<int:post_id>/", 
        views.toggle_vote, 
        name="toggle_vote"
    ),  # Vote on post (thumbs up/down)


    # ========================================================================
    # SECTION 4: COMMENTS SYSTEM
    # ========================================================================
    # Comment creation, editing, and deletion with nested replies

    path(
        "add-comment/<int:post_id>/", 
        views.add_comment, 
        name="add_comment"
    ),  # Add comment or reply to post

    path(
        "edit-comment/<int:comment_id>/", 
        views.edit_comment, 
        name="edit_comment"
    ),  # Edit own comment (PUT)

    path(
        "delete-comment/<int:comment_id>/", 
        views.delete_comment, 
        name="delete_comment"
    ),  # Delete own comment (POST)


    # ========================================================================
    # SECTION 5: SOCIAL ACTIONS (Follow & Block)
    # ========================================================================
    # User relationship management

    path(
        "toggle-follow/<str:username>/", 
        views.toggle_follow, 
        name="toggle_follow"
    ),  # Follow/unfollow user

    path(
        "toggle-block/<str:username>/", 
        views.toggle_block, 
        name="toggle_block"
    ),  # Block/unblock user

    path(
        "unblock/<str:username>/", 
        views.unblock_user, 
        name="unblock_user"
    ),  # Explicit unblock action

    path(
        "api/check-interaction/<str:username>/", 
        views.check_interaction, 
        name="check_interaction"
    ),  # Check if interaction allowed (not blocked)


    # ========================================================================
    # SECTION 6: NOTIFICATIONS
    # ========================================================================
    # Activity notifications and alerts

    path(
        "notifications", 
        views.notifications_view, 
        name="notifications"
    ),  # Notifications page

    path(
        "api/mark-notifications-read", 
        views.mark_notifications_read, 
        name="mark_notifications_read"
    ),  # Mark specific notifications as read (API)

    path(
        "mark-notifications-read/", 
        views.mark_all_notifications_read, 
        name="mark_notifications_read"
    ),  # Mark all notifications as read

    path(
        "clear-notifications/", 
        views.clear_all_notifications, 
        name="clear_notifications"
    ),  # Clear all notifications

    path(
        "delete-notification/<int:notification_id>/", 
        views.delete_notification, 
        name="delete_notification"
    ),  # Delete single notification


    # ========================================================================
    # SECTION 7: MESSAGING SYSTEM
    # ========================================================================
    # Direct messages and conversation management

    path(
        "messages/", 
        views.messages_inbox, 
        name="messages_inbox"
    ),  # Messages inbox (all conversations)

    path(
        "messages/<str:username>/", 
        views.conversation, 
        name="conversation"
    ),  # Legacy DM conversation (username-based)

    path(
        "messages/room/<int:conversation_id>/", 
        views.conversation_room, 
        name="conversation_room"
    ),  # Modern conversation room (ID-based)

    path(
        "delete-message/<int:message_id>/", 
        views.delete_message, 
        name="delete_message"
    ),  # Delete single message (own messages only)

    path(
        "delete-conversation/<str:username>/", 
        views.delete_conversation, 
        name="delete_conversation"
    ),  # Hide legacy DM conversation

    path(
        "delete-room/<int:conversation_id>/", 
        views.delete_room, 
        name="delete_room"
    ),  # Hide conversation room


    # ========================================================================
    # SECTION 8: GROUP MANAGEMENT
    # ========================================================================
    # Group conversation creation and administration

    # --- Group Creation & Membership ---

    path(
        "conversation/create-group/", 
        views.create_group, 
        name="create_group"
    ),  # Create new group conversation

    path(
        "conversation/add/<int:conversation_id>/", 
        views.add_to_conversation, 
        name="add_to_conversation"
    ),  # Add user to group

    path(
        "conversation/<int:conversation_id>/remove/<int:user_id>/", 
        views.remove_member, 
        name="remove_member"
    ),  # Remove member from group (admin only)

    path(
        "conversation/<int:conversation_id>/leave/", 
        views.leave_conversation, 
        name="leave_conversation"
    ),  # Leave group (self-removal)

    # --- Admin & Permissions ---

    path(
        "conversation/<int:conversation_id>/make-admin/<int:user_id>/", 
        views.make_group_admin, 
        name="make_group_admin"
    ),  # Promote member to admin

    path(
        "conversation/<int:conversation_id>/remove-admin/<int:user_id>/", 
        views.remove_group_admin, 
        name="remove_group_admin"
    ),  # Demote admin to member

    path(
        "conversation/<int:conversation_id>/transfer-owner/<int:user_id>/", 
        views.transfer_group_owner, 
        name="transfer_group_owner"
    ),  # Transfer ownership to another admin

    # --- Group Settings ---

    path(
        "conversation/<int:conversation_id>/update-name/", 
        views.update_group_name, 
        name="update_group_name"
    ),  # Update group name

    path(
        "conversation/<int:conversation_id>/avatar/", 
        views.update_group_avatar, 
        name="update_group_avatar"
    ),  # Update group avatar

    path(
        "conversation/<int:conversation_id>/delete/", 
        views.delete_group, 
        name="delete_group"
    ),  # Delete group (creator only)


    # ========================================================================
    # SECTION 9: TYPING INDICATORS
    # ========================================================================
    # Real-time typing status for messaging

    # --- Room-Based Typing (Modern, Group-Compatible) ---

    path(
        "api/typing/start/<int:room_id>/", 
        views.start_typing_room, 
        name="start_typing_room"
    ),  # Start typing in room

    path(
        "api/typing/stop/<int:room_id>/", 
        views.stop_typing_room, 
        name="stop_typing_room"
    ),  # Stop typing in room

    path(
        "api/typing/check/<int:room_id>/", 
        views.check_typing_room, 
        name="check_typing_room"
    ),  # Check who is typing in room

    # --- Legacy DM Typing (Username-Based) ---

    path(
        "api/typing/start/<str:username>/", 
        views.start_typing
    ),  # Start typing to user (legacy)

    path(
        "api/typing/stop/<str:username>/", 
        views.stop_typing
    ),  # Stop typing to user (legacy)

    path(
        "api/typing/check/<str:username>/", 
        views.check_typing
    ),  # Check typing status (legacy)


    # ========================================================================
    # SECTION 10: API ENDPOINTS
    # ========================================================================
    # RESTful API for AJAX operations

    # --- User Search & Mentions ---

    path(
        "users/search/", 
        views.users_search, 
        name="users_search"
    ),  # User search API (for adding to groups)

    path(
        "api/mentions/users/", 
        views.mention_user_suggestions, 
        name="mention_user_suggestions"
    ),  # Global user mention autocomplete

    path(
        "api/mentions/group/<int:conversation_id>/", 
        views.mention_group_suggestions, 
        name="mention_group_suggestions"
    ),  # Group member mention autocomplete

    # --- PWA & Notifications ---
    path(
        "api/message-badge/", 
        views.api_message_badge,
        name="api_message_badge"
    ),  # Unread message count for PWA badge

    path(
        "api/user-settings/", 
        views.api_user_settings,
        name="api_user_settings"
    ),  # Get user notification settings

    path(
        "api/update-message-settings/", 
        views.update_message_settings, 
        name="update_message_settings"
    ),  

    # ========================================================================
    # SECTION 11: MEDIA & GIF INTEGRATION
    # ========================================================================
    # Media uploads and external content integration

    path(
        "search-gifs/", 
        views.search_gifs, 
        name="search_gifs"
    ),  # Tenor GIF search API proxy


    # ========================================================================
    # SECTION 12: PRIVACY & SETTINGS
    # ========================================================================
    # User privacy controls and preferences

    path(
        "privacy-settings/", 
        views.privacy_settings, 
        name="privacy_settings"
    ),  # Privacy settings page

    path(
        "submit-report/", 
        views.submit_report, 
        name="submit_report"
    ),  # Report content/user (moderation)


    # ========================================================================
    # SECTION 13: PASSWORD RESET FLOW
    # ========================================================================
    # Django built-in password reset views with custom templates

    path(
        "password-reset/", 
        auth_views.PasswordResetView.as_view(
            template_name="network/password_reset.html",
            email_template_name="network/emails/password_reset_email.html",
            html_email_template_name="network/emails/password_reset_email.html",
            subject_template_name="network/password_reset_subject.txt",
        ), 
        name="password_reset"
    ),  # Request password reset (email form)

    path(
        "password-reset/done/", 
        auth_views.PasswordResetDoneView.as_view(
            template_name="network/password_reset_done.html"
        ), 
        name="password_reset_done"
    ),  # Password reset email sent confirmation

    path(
        "password-reset/confirm/<uidb64>/<token>/", 
        auth_views.PasswordResetConfirmView.as_view(
            template_name="network/password_reset_confirm.html"
        ), 
        name="password_reset_confirm"
    ),  # Password reset form (from email link)

    path(
        "password-reset/complete/", 
        auth_views.PasswordResetCompleteView.as_view(
            template_name="network/password_reset_complete.html"
        ), 
        name="password_reset_complete"
    ),  # Password reset success page
]


# ============================================================================
# SECTION 14: DEVELOPMENT MEDIA SERVING
# ============================================================================
# Serve user-uploaded media files during development
# WARNING: Not for production! 

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, 
        document_root=settings.MEDIA_ROOT
    )


"""
================================================================================
END OF URL CONFIGURATION
================================================================================

TOTAL ENDPOINTS: 75+ URL patterns organized into 14 logical sections

URL TESTING EXAMPLES
================================================================================
# Test URL resolution
from django.urls import reverse

# Core pages
home_url = reverse('index')  # '/'
profile_url = reverse('profile', kwargs={'username': 'john'})  # '/profile/john'

# Posts
post_url = reverse('post_detail', kwargs={'post_id': 123})  # '/post/123/'
vote_url = reverse('toggle_vote', kwargs={'post_id': 123})  # '/vote/123/'

# Messaging
inbox_url = reverse('messages_inbox')  # '/messages/'
room_url = reverse('conversation_room', kwargs={'conversation_id': 5})

# API endpoints
search_url = reverse('users_search')  # '/users/search/'
mentions_url = reverse('mention_user_suggestions')  # '/api/mentions/users/'


MAINTAINER
================================================================================
Argon Admin(Mahmudur Rahman)
Last updated: February 2026

================================================================================
"""
