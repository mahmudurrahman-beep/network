"""
================================================================================
ARGON SOCIAL NETWORK - MESSAGE INBOX FILTERS
================================================================================

@file        message_filters.py
@description Template filter for rendering media in message inbox previews
@version     1.0.0
@author      Argon Admin
@date        February 2026
@copyright   Copyright (c) 2026 Argon Social Network

MODULE PURPOSE
================================================================================
This module provides template filters specifically designed for the messages
inbox view. It renders GIFs and stickers as small inline thumbnails in the
message preview area.

USAGE IN TEMPLATES
================================================================================
Load the filter at the top of your template:

    {% load message_filters %}

Apply to message preview content:

    {{ message.content|parse_inbox_media|safe|truncatechars:60 }}

EXAMPLE
================================================================================
Input:  "Hey! [GIF:https://media.tenor.com/abc.gif] Check this [STICKER:https://cdn.example.com/smile.png]"
Output: "Hey! <img src='https://...' style='height:18px;...'> Check this <img src='https://...'>"

================================================================================
"""

from django import template
from django.utils.safestring import mark_safe
import re

# Register template tag library
register = template.Library()


@register.filter
def parse_inbox_media(content):
    """
    Parse media tags for inbox message preview.
    
    Renders GIFs and stickers as small inline thumbnails.
    Format: [GIF:url] and [STICKER:url]
    
    Args:
        content: Message content string
        
    Returns:
        HTML string with media rendered as small thumbnails
    """
    if not content:
        return ""
    
    text = str(content)
    
    # Replace GIF tags with small thumbnails
    def replace_media(match):
        tag_type = match.group(1).upper()  # GIF or STICKER
        url = match.group(2).strip()
        
        # Security: Only allow http/https URLs
        if not url.startswith(("http://", "https://")):
            return match.group(0)  # Leave as-is if invalid
        
        if tag_type == "GIF":
            return (
                f'<img src="{url}" '
                f'alt="GIF" '
                f'style="height:18px; width:auto; vertical-align:middle; margin:0 2px; border-radius:3px;" '
                f'class="inbox-media-preview">'
            )
        elif tag_type == "STICKER":
            return (
                f'<img src="{url}" '
                f'alt="Sticker" '
                f'style="height:18px; width:auto; vertical-align:middle; margin:0 2px;" '
                f'class="inbox-media-preview">'
            )
        
        return match.group(0)
    
    # Apply regex replacement
    parsed = re.sub(
        r"\[(GIF|STICKER):\s*([^\]]+?)\s*\]",
        replace_media,
        text,
        flags=re.IGNORECASE
    )
    
    return mark_safe(parsed)


@register.filter
def parse_inbox_media_text(content):
    """
    Alternative filter that shows emoji indicators instead of thumbnails.
    
    Args:
        content: Message content string
        
    Returns:
        Text with emoji indicators (🎬 GIF, 😊 Sticker)
    """
    if not content:
        return "(media)"
    
    text = str(content)
    
    # Replace GIF tags with emoji indicator
    text = re.sub(
        r'\[GIF:\s*[^\]]+?\s*\]',
        '🎬 GIF',
        text,
        flags=re.IGNORECASE
    )
    
    # Replace sticker tags with emoji indicator
    text = re.sub(
        r'\[STICKER:\s*[^\]]+?\s*\]',
        '😊 Sticker',
        text,
        flags=re.IGNORECASE
    )
    
    return text


"""
================================================================================
END OF MESSAGE FILTERS
================================================================================
""" 
