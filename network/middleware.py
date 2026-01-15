import pytz
from django.utils import timezone

class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                tz = pytz.timezone(request.user.timezone)
                timezone.activate(tz)
            except (pytz.UnknownTimeZoneError, AttributeError):
                timezone.activate(pytz.UTC)
        else:
            timezone.activate(pytz.UTC)
        
        response = self.get_response(request)
        return response
    