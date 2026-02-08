from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    User, Post, PostMedia, Follow, Notification, Message,
    Conversation, ConversationMember, Block, PrivacySettings,
    Comment
)

# ==================== ADMIN CLASSES ====================

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_superuser', 'date_joined')
    search_fields = ('username', 'email')
    actions = ['activate_users', 'deactivate_users']
    
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} users activated")
    activate_users.short_description = "Activate selected users"
    
    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} users deactivated")
    deactivate_users.short_description = "Deactivate selected users"

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_link', 'timestamp', 'content_short')
    search_fields = ('content', 'user__username')
    
    def user_link(self, obj):
        url = reverse("admin:network_user_change", args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'
    
    def content_short(self, obj):
        if obj.content:
            return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
        return "(no content)"
    content_short.short_description = 'Content'

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'actor', 'verb', 'created_at', 'is_read')
    list_filter = ('is_read', 'created_at')
    search_fields = ('user__username', 'actor__username', 'verb')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'recipient', 'timestamp', 'content_short')
    list_filter = ('is_read', 'timestamp')
    search_fields = ('content', 'sender__username', 'recipient__username')
    
    def content_short(self, obj):
        if obj.content:
            return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
        return "(media)"
    content_short.short_description = 'Content'

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_group', 'created_by', 'created_at', 'member_count')
    list_filter = ('is_group', 'created_at')
    search_fields = ('name', 'created_by__username')
    
    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'

@admin.register(ConversationMember)
class ConversationMemberAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'user', 'joined_at', 'is_admin')
    list_filter = ('is_admin', 'joined_at')
    search_fields = ('conversation__name', 'user__username')

@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ('id', 'blocker', 'blocked', 'timestamp')
    search_fields = ('blocker__username', 'blocked__username')

@admin.register(PrivacySettings)
class PrivacySettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'post_visibility')
    list_filter = ('post_visibility',)
    search_fields = ('user__username',)

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'post', 'timestamp', 'content_short')
    search_fields = ('content', 'user__username', 'post__id')
    
    def content_short(self, obj):
        if obj.content:
            return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
        return "(no content)"
    content_short.short_description = 'Content'

@admin.register(PostMedia)
class PostMediaAdmin(admin.ModelAdmin):
    list_display = ('id', 'post', 'media_type')
    list_filter = ('media_type',)

@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('id', 'follower', 'followed')
    search_fields = ('follower__username', 'followed__username')

# Unregister Django's default Group
admin.site.unregister(Group)

# Basic admin site configuration
admin.site.site_header = "Argon Network Admin"
admin.site.site_title = "Argon Network Admin Portal"
admin.site.index_title = "Welcome"  
