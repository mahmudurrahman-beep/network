from django.contrib import admin
from .models import User, Post, PostMedia, Follow, Notification, Message, Comment

# Register all models for superuser
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'timezone', 'last_login')
    search_fields = ('username', 'email')

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('user', 'content', 'timestamp')
    search_fields = ('content',)
    list_filter = ('user', 'timestamp')
    actions = ['delete_selected']  # bulk delete

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('post', 'user', 'content', 'timestamp', 'media_preview')
    search_fields = ('content',)
    list_filter = ('post', 'user', 'timestamp')
    readonly_fields = ('timestamp',)

    def media_preview(self, obj):
        if obj.media:
            if obj.media_type == 'image' or obj.media_type == 'gif':
                return format_html('<img src="{}" width="100" />', obj.media.url)
            elif obj.media_type == 'video':
                return format_html('<video width="100" controls><source src="{}" type="video/mp4"></video>', obj.media.url)
        return "No media"
    media_preview.short_description = 'Media Preview'

    
@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'content', 'timestamp', 'is_read')
    search_fields = ('content',)
    list_filter = ('sender', 'recipient', 'is_read')
    actions = ['delete_selected']  # superuser can delete any chat

@admin.register(PostMedia)
class PostMediaAdmin(admin.ModelAdmin):
    list_display = ('post', 'media_type', 'file')

@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('follower', 'followed')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'actor', 'verb', 'created_at', 'is_read')