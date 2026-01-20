from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Safely get item from dictionary.
    Returns the value if key exists, otherwise returns False.
    """
    if isinstance(dictionary, dict):
        return dictionary.get(str(key), False)
    return False