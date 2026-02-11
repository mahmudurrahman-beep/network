from django import template
from django.urls import reverse
import re

register = template.Library()

@register.filter
def parse_media(value):
    """
    Django template filter to parse media tags and mentions in text content.
    
    Supports:
    - @mentions: Converts @username to clickable profile links
    - [GIF:url]: Renders GIF images
    - [STICKER:url]: Renders sticker images
    - Line breaks: Converts \n to <br>
    """
    if not value:
        return value
    
    # Convert @mentions to profile links
    def replace_mention(match):
        username = match.group(1)
        try:
            url = reverse('profile', args=[username])
        except:
            url = f'/profile/{username}/'
        return f'<a href="{url}">@{username}</a>'
    
    value = re.sub(
        r'(?<![<@\w])@(\w+)(?![^<]*>)',
        replace_mention,
        value
    )
    
    # Find [GIF:url] and [STICKER:url]
    def replace_tag(match):
        tag_type, url = match.groups()
        if tag_type == 'GIF':
            return f'<img src="{url}" class="img-fluid rounded mt-2" style="max-width: 300px;" alt="GIF">'
        elif tag_type == 'STICKER':
            return f'<img src="{url}" class="img-fluid rounded mt-2" style="max-width: 150px; background: transparent;" alt="Sticker">'
        return match.group(0)
    
    # Regex: [GIF:https://...] or [STICKER:https://...]
    parsed = re.sub(
        r'\[(GIF|STICKER):([^]]+)\]',
        replace_tag,
        value,
        flags=re.IGNORECASE
    )
    
    # Preserve line breaks
    return parsed.replace('\n', '<br>')
