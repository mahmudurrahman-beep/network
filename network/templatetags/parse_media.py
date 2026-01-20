from django import template
import re

register = template.Library()

@register.filter
def parse_media(value):
    if not value:
        return value
    
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
