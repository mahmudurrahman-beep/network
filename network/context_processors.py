from .models import Notification
from django.contrib.auth.decorators import login_required

# network/context_processors.py

# network/context_processors.py

def unread_counts(request):
    """
    Context processor that adds unread counts to every template context.
    """
    if request.user.is_authenticated:
        # Count unread messages (received and not read)
        unread_messages = request.user.received_messages.filter(is_read=False).count()
        
        # Count unread notifications EXCLUDING message notifications
        unread_notifications = request.user.notifications.filter(
            is_read=False
        ).exclude(
            verb__icontains="message"  # Exclude any notification about messages
        ).count()
        
        return {
            'unread_messages_count': unread_messages,
            'unread_notifications_count': unread_notifications,
        }
    
    # Return empty dict for unauthenticated users
    return {}