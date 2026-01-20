# network/templatetags/comment_filters.py
from django import template

register = template.Library()

@register.filter
def get_root_comments(comments):
    """Return only root comments (comments with no parent)"""
    return comments.filter(parent__isnull=True)

@register.filter
def get_replies(comment):
    """Return replies for a comment"""
    return comment.replies.all()