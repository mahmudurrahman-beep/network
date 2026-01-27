from django.contrib.auth.models import AbstractUser
from django.db import models
import pytz

TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.all_timezones]
GENDER_CHOICES = [
    ('M', 'Male'),
    ('F', 'Female'),
    ('O', 'Other'),
    ('N', 'Prefer not to say'),
]

class User(AbstractUser):
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    hidden_conversations = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='hidden_by')
    timezone = models.CharField(max_length=100, choices=TIMEZONE_CHOICES, default='UTC')
    activation_token = models.CharField(max_length=32, blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    is_private = models.BooleanField(default=False)  

class Post(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    thumbs_up = models.ManyToManyField(User, related_name='upvoted_posts', blank=True)
    thumbs_down = models.ManyToManyField(User, related_name='downvoted_posts', blank=True)
    class Meta:
        ordering = ['-timestamp']
    def __str__(self):
        return f"{self.user} - {self.content[:50]}"

class PostMedia(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='media')
    file = models.FileField(upload_to='post_media/')
    media_type = models.CharField(max_length=10, choices=[('image', 'Image'), ('video', 'Video')])

class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    followed = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    class Meta:
        unique_together = ('follower', 'followed')

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    verb = models.CharField(max_length=50) # e.g., "liked", "followed"
    post = models.ForeignKey(Post, on_delete=models.SET_NULL, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']

class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    media = models.FileField(upload_to='message_media/', blank=True, null=True)
    media_url = models.URLField(max_length=500, null=True, blank=True)  # Added for external GIFs/Stickers
    media_type = models.CharField(max_length=10, choices=[('image', 'Image'), ('video', 'Video'), ('gif', 'GIF'), ('sticker', 'Sticker')], blank=True)
    class Meta:
        ordering = ['-timestamp']
    def __str__(self):
        return f"{self.sender} to {self.recipient}: {self.content[:30]}"

class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')  # Added from local for nesting
    timestamp = models.DateTimeField(auto_now_add=True)
    media = models.FileField(upload_to='comment_media/', blank=True, null=True)
    media_url = models.URLField(max_length=500, null=True, blank=True)  # Added from local for GIFs
    media_type = models.CharField(max_length=10, choices=[('image', 'Image'), ('video', 'Video'), ('gif', 'GIF'), ('sticker', 'Sticker')], blank=True)
    class Meta:
        ordering = ['-timestamp']       

class Block(models.Model):
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocks')
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_by')
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('blocker', 'blocked')  # No duplicate blocks

class PrivacySettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='privacy')
    post_visibility = models.CharField(
        max_length=10,
        choices=[
            ('followers', 'Followers Only'),
            ('following', 'Following Only'),
            ('both', 'Followers & Following'),
            ('universal', 'Everyone')
        ],
        default='universal'
    )     
        

