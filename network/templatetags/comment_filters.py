# network/templatetags/comment_filters.py
from django import template
from django.db.models import Q

register = template.Library()

@register.filter
def get_root_comments(comments):
    """Return only root comments (comments with no parent)"""
    return comments.filter(parent__isnull=True)

@register.filter
def get_replies(comment):
    """Return replies for a comment"""
    return comment.replies.all()

@register.filter
def filter_by_privacy(comments, request_user):
    """Filter comments based on privacy settings"""
    if not request_user.is_authenticated:
        return comments.filter(user__is_private=False)
    
    # Check blocks using the Block model
    blocked_users = request_user.blocks.values_list('blocked', flat=True)
    blocked_by_users = request_user.blocked_by.values_list('blocker', flat=True)
    
    # Exclude comments from users who blocked specific user or the user blocked
    return comments.exclude(
        user_id__in=blocked_users
    ).exclude(
        user_id__in=blocked_by_users
    ).filter(
        Q(user__is_private=False) |
        Q(user__followers__follower=request_user) |  
        Q(user=request_user)
    ).distinct()

@register.simple_tag
def can_comment_on_post(post, user):
    """Check if user can comment on a post"""
    if not user.is_authenticated:
        return False
    
    # Check if post author has blocked user
    if post.user.blocks.filter(blocked=user).exists():
        return False
    
    # Check if user has blocked post author
    if user.blocks.filter(blocked=post.user).exists():
        return False
    
    # Check if private account and not following
    if post.user.is_private and not post.user.followers.filter(follower=user).exists():
        return False
    
    return True   


@register.filter
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(str(key), False)
    return False

@register.filter
def sub(value, arg):
    try:
        return int(value) - int(arg)
    except Exception:
        try:
            return float(value) - float(arg)
        except Exception:
            return 0

@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except Exception:
        return 0
