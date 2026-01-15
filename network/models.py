from django.contrib.auth.models import AbstractUser
from django.db import models
import pytz

TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.all_timezones]

class User(AbstractUser):
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    hidden_conversations = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='hidden_by')  
    timezone = models.CharField(max_length=100, choices=TIMEZONE_CHOICES, default='UTC')
    activation_token = models.CharField(max_length=32, blank=True, null=True)
    
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
    verb = models.CharField(max_length=50)  # e.g., "liked", "followed"
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

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.sender} to {self.recipient}: {self.content[:30]}" 
    
class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    media = models.FileField(upload_to='comment_media/', blank=True, null=True)
    media_type = models.CharField(max_length=10, choices=[('image', 'Image'), ('video', 'Video'), ('gif', 'GIF')], blank=True)

    class Meta:
        ordering = ['-timestamp']