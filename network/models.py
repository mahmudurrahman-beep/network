"""
================================================================================
ARGON SOCIAL NETWORK - DATABASE MODELS
================================================================================

@file        models.py
@description Django ORM models defining the complete database schema
@version     2.0.0
@author      Argon Admin
@date        February 2026
@copyright   Copyright (c) 2026 Argon Social Network

MODULE PURPOSE
================================================================================
This module defines all database models for the Argon Social Network platform:
- User model (extended from AbstractUser)
- Posts and media content
- Comments with nested replies
- Social relationships (Follow, Block)
- Messaging system (Conversations, Messages)
- Notifications
- Privacy settings

DATABASE STRUCTURE
================================================================================
1. User & Authentication
   - User (AbstractUser extension)
   - PrivacySettings (OneToOne with User)

2. Content Models
   - Post (user-generated content)
   - PostMedia (attached images/videos)
   - Comment (post comments with nesting)

3. Social Relationships
   - Follow (follower/following connections)
   - Block (user blocking system)

4. Messaging System
   - Conversation (DM and group chats)
   - ConversationMember (membership tracking)
   - Message (chat messages)

5. Notifications
   - Notification (activity alerts)

DEPENDENCIES
================================================================================
- Django 4.x+
- django.contrib.auth.models.AbstractUser
- pytz (timezone support)
- Pillow (image handling)

MODEL RELATIONSHIPS
================================================================================
User (1) ──────> (N) Post
User (1) ──────> (N) Comment
User (1) ──────> (N) Message
User (1) ──────> (N) Notification
User (1) ──────> (1) PrivacySettings

Post (1) ──────> (N) PostMedia
Post (1) ──────> (N) Comment
Comment (1) ────> (N) Comment (nested replies)

User (N) <─────> (N) User (Follow, Block)
User (N) <─────> (N) Conversation (via ConversationMember)

FEATURES
================================================================================
- Custom user model with profile fields
- Timezone support per user
- Online status tracking (5-minute window)
- Typing indicators for messaging
- Nested comments (parent-child relationships)
- Group conversations with admin roles
- Media attachments (images, videos, GIFs)
- Privacy controls per user
- PWA badge and sound notifications
- Email activation tokens

TIMEZONE HANDLING
================================================================================
All timestamp fields use Django's timezone-aware datetime.
Users can set their preferred timezone from pytz.all_timezones.

MEDIA HANDLING
================================================================================
Media files are organized in subdirectories:
- profile_pics/     : User avatars
- group_avatars/    : Group conversation avatars
- post_media/       : Post attachments
- comment_media/    : Comment attachments
- message_media/    : Message attachments

PRIVACY & SECURITY
================================================================================
- User blocking (bidirectional prevention)
- Privacy settings for post visibility
- Hidden conversations support
- Optional birth date visibility controls
- Activation token for email verification

PERFORMANCE CONSIDERATIONS
================================================================================
- Indexed fields: timestamp (ordering)
- ManyToMany fields optimized for frequent queries
- ForeignKey on_delete policies carefully chosen
- Meta ordering for chronological displays

================================================================================
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
import pytz
from django.utils import timezone as dj_timezone
from datetime import timedelta
from cloudinary.models import CloudinaryField

# ============================================================================
# CONSTANTS & CHOICES
# ============================================================================

"""
Timezone choices for user preference selection.
Uses all available timezones from pytz library.
"""
TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.all_timezones]

"""
Gender choices for user profile.
Includes prefer not to say option for privacy.
"""
GENDER_CHOICES = [
    ('M', 'Male'),
    ('F', 'Female'),
    ('O', 'Other'),
    ('N', 'Prefer not to say'),
]


# ============================================================================
# SECTION 1: USER & AUTHENTICATION MODELS
# ============================================================================

class User(AbstractUser):
    """
    Extended User model with social network features.

    Extends Django's AbstractUser with additional fields for:
    - Profile customization (picture, bio, banner)
    - Social features (followers, blocking)
    - Messaging (conversations, typing indicators)
    - Privacy settings (birth date visibility)
    - Presence tracking (online status, last seen)
    - Notification preferences (PWA badges, sounds)

    Attributes:
        profile_picture (ImageField): User avatar image
        bio (TextField): Profile biography (max 500 chars)
        hidden_conversations (ManyToManyField): Conversations hidden by user
        timezone (CharField): User's preferred timezone
        activation_token (CharField): Email verification token
        gender (CharField): Gender identity (optional)
        birth_date (DateField): Date of birth (optional)
        birth_year_hidden (BooleanField): Hide birth year in profile
        birth_date_hidden (BooleanField): Hide entire birth date
        last_seen (DateTimeField): Last activity timestamp
        is_typing (BooleanField): Currently typing indicator
        typing_to (ForeignKey): User being typed to
        last_typing_time (DateTimeField): Last typing activity time
        message_badge_enabled (BooleanField): Show unread message badge
        message_sound_enabled (BooleanField): Play sound for new messages
        message_sound_choice (CharField): Sound effect selection
        is_private (BooleanField): Private profile flag

    Properties:
        is_online: True if user was active in last 5 minutes

    Related Names:
        posts: QuerySet of user's Post objects
        comments: QuerySet of user's Comment objects
        sent_messages: QuerySet of sent Message objects
        received_messages: QuerySet of received Message objects
        following: QuerySet of Follow objects (users this user follows)
        followers: QuerySet of Follow objects (users following this user)
        blocks: QuerySet of Block objects (users blocked by this user)
        blocked_by: QuerySet of Block objects (users who blocked this user)
        notifications: QuerySet of Notification objects

    Example:
        user = User.objects.get(username='john')
        if user.is_online:
            print(f"{user.username} is currently online")
    """

    # --- Profile Information ---
    profile_picture = models.ImageField(
        upload_to='profile_pics/', 
        null=True, 
        blank=True,
        help_text="User's profile avatar image"
    )
    bio = models.TextField(
        max_length=500, 
        blank=True,
        help_text="Profile biography or description"
    )

    # --- Privacy & Display ---
    hidden_conversations = models.ManyToManyField(
        'self', 
        symmetrical=False, 
        blank=True, 
        related_name='hidden_by',
        help_text="Conversations hidden from user's inbox"
    )
    timezone = models.CharField(
        max_length=100, 
        choices=TIMEZONE_CHOICES, 
        default='UTC',
        help_text="User's preferred timezone for display"
    )

    # --- Authentication ---
    activation_token = models.CharField(
        max_length=32, 
        blank=True, 
        null=True,
        help_text="Token for email verification"
    )

    # --- Personal Information ---
    gender = models.CharField(
        max_length=1, 
        choices=GENDER_CHOICES, 
        blank=True,
        help_text="Gender identity (optional)"
    )
    birth_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Date of birth for zodiac sign calculation"
    )
    birth_year_hidden = models.BooleanField(
        default=False,
        help_text="Hide birth year, show only month/day"
    )
    birth_date_hidden = models.BooleanField(
        default=False,
        help_text="Hide entire birth date from profile"
    )

    # --- Presence & Activity Tracking ---
    last_seen = models.DateTimeField(
        null=True, 
        blank=True, 
        default=dj_timezone.now,
        help_text="Last activity timestamp for online status"
    )
    is_typing = models.BooleanField(
        default=False,
        help_text="Currently typing indicator"
    )
    typing_to = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='typing_from',
        help_text="User this user is currently typing to"
    )
    last_typing_time = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Timestamp of last typing activity"
    )

    # --- Notification Preferences ---
    message_badge_enabled = models.BooleanField(
        default=True,
        help_text="Show unread message count in PWA/browser badge"
    )
    message_sound_enabled = models.BooleanField(
        default=True,
        help_text="Play sound notification for new messages"
    )
    message_sound_choice = models.CharField(
        max_length=20,
        choices=[
            ("ding", "Ding"),
            ("pop", "Pop"),
            ("chime", "Chime"),
        ],
        default="ding",
        help_text="Sound effect for message notifications"
    )

    # --- Privacy Flags ---
    is_private = models.BooleanField(
        default=False,
        help_text="Private profile (followers-only visibility)"
    )

    @property
    def is_online(self):
        """
        Determine if user is currently online.

        A user is considered online if their last_seen timestamp
        is within the last 5 minutes.

        Returns:
            bool: True if user is online, False otherwise

        Example:
            if request.user.is_online:
                # Show green status indicator
        """
        if not self.last_seen:
            return False
        return dj_timezone.now() - self.last_seen < timedelta(minutes=5)


# ============================================================================
# SECTION 2: CONTENT MODELS (Posts & Media)
# ============================================================================

class Post(models.Model):
    """
    User-generated post content.

    Represents a social media post with text content and optional media.
    Supports voting system (thumbs up/down) and comments.

    Attributes:
        user (ForeignKey): Post author
        content (TextField): Post text content
        timestamp (DateTimeField): Creation datetime
        thumbs_up (ManyToManyField): Users who upvoted
        thumbs_down (ManyToManyField): Users who downvoted

    Related Names:
        media: QuerySet of PostMedia objects (attachments)
        comments: QuerySet of Comment objects

    Meta:
        ordering: Newest first (descending timestamp)

    Example:
        post = Post.objects.create(user=request.user, content="Hello world!")
        post.thumbs_up.add(other_user)
    """

    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='posts',
        help_text="Author of this post"
    )
    content = models.TextField(
        help_text="Post text content"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="Creation timestamp"
    )
    thumbs_up = models.ManyToManyField(
        User, 
        related_name='upvoted_posts', 
        blank=True,
        help_text="Users who upvoted this post"
    )
    thumbs_down = models.ManyToManyField(
        User, 
        related_name='downvoted_posts', 
        blank=True,
        help_text="Users who downvoted this post"
    )

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} - {self.content[:50]}"


class PostMedia(models.Model):
    """
    Media attachments for posts.

    Stores images or videos attached to a post.
    Multiple media files can be attached to a single post.

    Attributes:
        post (ForeignKey): Associated post
        file (CloudinaryField): Media file (image or video) - auto-detects type
        media_type (CharField): Type of media ('image' or 'video')

    Example:
        media = PostMedia.objects.create(
            post=post,
            file=uploaded_file,
            media_type='image'
        )
    """

    post = models.ForeignKey(
        Post, 
        on_delete=models.CASCADE, 
        related_name='media',
        help_text="Post this media belongs to"
    )
    # ✅ CHANGED: CloudinaryField instead of FileField
    file = CloudinaryField(
        'media',
        resource_type='auto',  # Auto-detects image vs video
        folder='post_media',
        help_text="Uploaded media file"
    )
    media_type = models.CharField(
        max_length=10, 
        choices=[('image', 'Image'), ('video', 'Video')],
        help_text="Type of media file"
    )

class Comment(models.Model):
    """
    Comment on a post with optional nested replies.

    Supports nested commenting with parent-child relationships.
    Can include media attachments (images, videos, GIFs).

    Attributes:
        user (ForeignKey): Comment author
        post (ForeignKey): Post being commented on
        content (TextField): Comment text content
        parent (ForeignKey): Parent comment (for nested replies)
        timestamp (DateTimeField): Creation datetime
        media (FileField): Optional media attachment
        media_url (URLField): External media URL (GIFs, stickers)
        media_type (CharField): Type of media

    Related Names:
        replies: QuerySet of child Comment objects (nested replies)

    Meta:
        ordering: Newest first (descending timestamp)

    Example:
        # Root comment
        comment = Comment.objects.create(user=user, post=post, content="Great post!")

        # Reply to comment
        reply = Comment.objects.create(
            user=other_user, 
            post=post, 
            content="Thanks!",
            parent=comment
        )
    """

    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='comments',
        help_text="Comment author"
    )
    post = models.ForeignKey(
        Post, 
        on_delete=models.CASCADE, 
        related_name='comments',
        help_text="Post being commented on"
    )
    content = models.TextField(
        help_text="Comment text content"
    )
    parent = models.ForeignKey(
        'self', 
        null=True, 
        blank=True, 
        on_delete=models.CASCADE, 
        related_name='replies',
        help_text="Parent comment for nested replies"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="Creation timestamp"
    )
    media = models.FileField(
        upload_to='comment_media/', 
        blank=True, 
        null=True,
        help_text="Optional media attachment"
    )
    media_url = models.URLField(
        max_length=500, 
        null=True, 
        blank=True,
        help_text="External media URL (GIFs, stickers)"
    )
    media_type = models.CharField(
        max_length=10, 
        choices=[
            ('image', 'Image'), 
            ('video', 'Video'), 
            ('gif', 'GIF'), 
            ('sticker', 'Sticker')
        ], 
        blank=True,
        help_text="Type of media"
    )

    class Meta:
        ordering = ['-timestamp']


# ============================================================================
# SECTION 3: SOCIAL RELATIONSHIP MODELS
# ============================================================================

class Follow(models.Model):
    """
    Follower-following relationship between users.

    Represents a one-way follow connection.
    User A can follow User B without B following back.

    Attributes:
        follower (ForeignKey): User who is following
        followed (ForeignKey): User being followed

    Meta:
        unique_together: Prevents duplicate follow relationships

    Example:
        # User A follows User B
        Follow.objects.create(follower=user_a, followed=user_b)

        # Check if following
        is_following = Follow.objects.filter(
            follower=request.user, 
            followed=profile_user
        ).exists()
    """

    follower = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='following',
        help_text="User who is following"
    )
    followed = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='followers',
        help_text="User being followed"
    )

    class Meta:
        unique_together = ('follower', 'followed')


class Block(models.Model):
    """
    User blocking relationship.

    Represents a one-way block.
    Prevents interactions between blocker and blocked user.

    Attributes:
        blocker (ForeignKey): User who initiated the block
        blocked (ForeignKey): User who is blocked
        timestamp (DateTimeField): When block was created

    Meta:
        unique_together: Prevents duplicate blocks

    Example:
        # User A blocks User B
        Block.objects.create(blocker=user_a, blocked=user_b)

        # Check if blocked
        is_blocked = Block.objects.filter(
            blocker=request.user, 
            blocked=other_user
        ).exists()
    """

    blocker = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='blocks',
        help_text="User who initiated the block"
    )
    blocked = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='blocked_by',
        help_text="User who is blocked"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="Block creation timestamp"
    )

    class Meta:
        unique_together = ('blocker', 'blocked')


# ============================================================================
# SECTION 4: MESSAGING SYSTEM MODELS
# ============================================================================

class Conversation(models.Model):
    """
    Chat conversation (DM or group).

    Represents a messaging conversation between two or more users.
    Can be a direct message (2 users) or group chat (3+ users).

    Attributes:
        name (CharField): Conversation name (for groups)
        is_group (BooleanField): True for group chats, False for DMs
        created_by (ForeignKey): User who created the conversation
        group_avatar (ImageField): Group avatar image
        created_at (DateTimeField): Creation timestamp
        hidden_by (ManyToManyField): Users who hid this conversation

    Related Names:
        members: QuerySet of ConversationMember objects
        messages: QuerySet of Message objects

    Example:
        # Create DM conversation
        dm = Conversation.objects.create(is_group=False)

        # Create group conversation
        group = Conversation.objects.create(
            name="Study Group",
            is_group=True,
            created_by=request.user
        )
    """

    name = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Conversation name (required for groups)"
    )
    is_group = models.BooleanField(
        default=False,
        help_text="True for group chats, False for DMs"
    )
    created_by = models.ForeignKey(
        User, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name='created_conversations',
        help_text="User who created this conversation"
    )
    group_avatar = models.ImageField(
        upload_to='group_avatars/', 
        null=True, 
        blank=True,
        help_text="Group avatar image"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Creation timestamp"
    )
    hidden_by = models.ManyToManyField(
        User, 
        blank=True, 
        related_name='hidden_rooms',
        help_text="Users who hid this conversation from their inbox"
    )

    def __str__(self):
        if self.is_group:
            return self.name or f"Group #{self.id}"
        return f"DM #{self.id}"


class ConversationMember(models.Model):
    """
    Membership in a conversation.

    Tracks users who are members of a conversation.
    Includes join time, last read tracking, and admin status.

    Attributes:
        conversation (ForeignKey): Conversation this membership belongs to
        user (ForeignKey): User who is a member
        joined_at (DateTimeField): When user joined
        last_read_at (DateTimeField): Last time user read messages
        is_admin (BooleanField): Admin privileges in group

    Meta:
        unique_together: One membership per user per conversation

    Example:
        # Add user to conversation
        member = ConversationMember.objects.create(
            conversation=group,
            user=new_user,
            is_admin=False
        )

        # Make user admin
        member.is_admin = True
        member.save()
    """

    conversation = models.ForeignKey(
        Conversation, 
        on_delete=models.CASCADE, 
        related_name='members',
        help_text="Conversation this membership belongs to"
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='conversation_memberships',
        help_text="User who is a member"
    )
    joined_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When user joined this conversation"
    )
    last_read_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Last time user read messages (for unread count)"
    )
    is_admin = models.BooleanField(
        default=False,
        help_text="Admin privileges in group conversation"
    )

    class Meta:
        unique_together = ('conversation', 'user')

    def __str__(self):
        return f"{self.user} in {self.conversation}"


class Message(models.Model):
    """
    Chat message in a conversation or DM.

    Represents a single message sent in a conversation.
    Supports both room-based (new) and legacy DM systems.
    Can include media attachments or external media URLs.

    Attributes:
        conversation (ForeignKey): Conversation this message belongs to
        sender (ForeignKey): User who sent the message
        recipient (ForeignKey): Direct recipient (legacy DM system)
        content (TextField): Message text content
        timestamp (DateTimeField): Creation timestamp
        is_read (BooleanField): Read status (DM only)
        media (FileField): Uploaded media attachment
        media_url (URLField): External media URL (GIFs, stickers)
        media_type (CharField): Type of media

    Meta:
        ordering: Newest first (descending timestamp)

    Example:
        # Send message in conversation
        message = Message.objects.create(
            conversation=room,
            sender=request.user,
            content="Hello everyone!"
        )

        # Send DM (legacy)
        dm = Message.objects.create(
            sender=request.user,
            recipient=other_user,
            content="Hey there!"
        )
    """

    conversation = models.ForeignKey(
        Conversation, 
        on_delete=models.CASCADE, 
        related_name='messages', 
        null=True, 
        blank=True,
        help_text="Conversation this message belongs to (room-based)"
    )
    sender = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='sent_messages',
        help_text="User who sent this message"
    )
    recipient = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='received_messages', 
        null=True, 
        blank=True,
        help_text="Direct recipient (legacy DM system)"
    )
    content = models.TextField(
        blank=True,
        help_text="Message text content"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="Message creation timestamp"
    )
    is_read = models.BooleanField(
        default=False,
        help_text="Read status (DM only, groups use last_read_at)"
    )
    media = models.FileField(
        upload_to='message_media/', 
        blank=True, 
        null=True,
        help_text="Uploaded media attachment"
    )
    media_url = models.URLField(
        max_length=500, 
        null=True, 
        blank=True,
        help_text="External media URL (GIFs, stickers)"
    )
    media_type = models.CharField(
        max_length=10,
        choices=[
            ('image', 'Image'), 
            ('video', 'Video'), 
            ('gif', 'GIF'), 
            ('sticker', 'Sticker')
        ],
        blank=True,
        help_text="Type of media content"
    )

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        if self.conversation_id:
            return f"[Room {self.conversation_id}] {self.sender}: {self.content[:30]}"
        return f"{self.sender} to {self.recipient}: {self.content[:30]}"


# ============================================================================
# SECTION 5: NOTIFICATION MODELS
# ============================================================================

class Notification(models.Model):
    """
    User activity notification.

    Represents a notification for user actions like likes, follows,
    comments, mentions, etc.

    Attributes:
        user (ForeignKey): User receiving the notification
        actor (ForeignKey): User who performed the action
        verb (CharField): Action description (e.g., "liked", "followed")
        post (ForeignKey): Associated post (if applicable)
        conversation (ForeignKey): Associated conversation (if applicable)
        is_read (BooleanField): Read status
        created_at (DateTimeField): Creation timestamp

    Meta:
        ordering: Newest first (descending created_at)

    Example:
        # Notify user of new follower
        Notification.objects.create(
            user=followed_user,
            actor=follower,
            verb="followed you"
        )

        # Notify user of post like
        Notification.objects.create(
            user=post.user,
            actor=liker,
            verb="liked your post",
            post=post
        )
    """

    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='notifications',
        help_text="User receiving this notification"
    )
    actor = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        help_text="User who performed the action"
    )
    verb = models.CharField(
        max_length=50,
        help_text="Action description (e.g., 'liked', 'followed', 'mentioned you')"
    )
    post = models.ForeignKey(
        Post, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Associated post (if applicable)"
    )
    conversation = models.ForeignKey(
        'Conversation', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Associated conversation (if applicable)"
    )
    is_read = models.BooleanField(
        default=False,
        help_text="Whether notification has been read"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Notification creation timestamp"
    )

    class Meta:
        ordering = ['-created_at']


# ============================================================================
# SECTION 6: PRIVACY & SETTINGS MODELS
# ============================================================================

class PrivacySettings(models.Model):
    """
    User privacy configuration.

    Controls post visibility and privacy preferences.
    OneToOne relationship with User model.

    Attributes:
        user (OneToOneField): Associated user
        post_visibility (CharField): Who can see user's posts
            - 'followers': Only followers
            - 'following': Only users being followed
            - 'both': Followers and following
            - 'universal': Everyone (public)

    Example:
        # Get or create privacy settings
        settings, created = PrivacySettings.objects.get_or_create(
            user=request.user,
            defaults={'post_visibility': 'universal'}
        )

        # Update visibility
        settings.post_visibility = 'followers'
        settings.save()
    """

    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='privacy',
        help_text="User these settings belong to"
    )
    post_visibility = models.CharField(
        max_length=10,
        choices=[
            ('followers', 'Followers Only'),
            ('following', 'Following Only'),
            ('both', 'Followers & Following'),
            ('universal', 'Everyone')
        ],
        default='universal',
        help_text="Who can view user's posts"
    )


"""
================================================================================
END OF MODELS DEFINITION
================================================================================

DATABASE MIGRATION NOTES
================================================================================
After modifying models, run:
1. python manage.py makemigrations
2. python manage.py migrate

TESTING RECOMMENDATIONS
================================================================================
- Test all foreign key relationships
- Verify CASCADE delete behavior
- Test unique_together constraints
- Verify ManyToMany relationships
- Test timezone-aware datetime fields

FUTURE ENHANCEMENTS
================================================================================
- Add Post edit history tracking
- Implement soft delete for messages
- Add conversation archiving
- Implement read receipts for group messages
- Add user reputation/karma system
- Implement content moderation flags

MAINTAINER
================================================================================
Argon Admin
Last updated: February 2026
================================================================================
"""
