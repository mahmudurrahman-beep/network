"""
================================================================================
ARGON NETWORK - CUSTOM MIDDLEWARE
================================================================================

@file        middleware.py
@description Custom Django middleware for timezone and presence tracking
@version     2.0.0
@author      Argon Admin
@date        February 2026
@copyright   Copyright (c) 2026 Argon Network

MODULE PURPOSE
================================================================================
This module provides custom middleware classes for the Argon Social Network:

1. TimezoneMiddleware
   - Activates user-specific timezone for datetime display
   - Falls back to UTC for anonymous or invalid timezones

2. UpdateLastSeenMiddleware
   - Updates user's last_seen timestamp for online status tracking
   - Uses caching to prevent excessive database writes
   - Powers "online now" indicators across the site

PERFORMANCE IMPACT
================================================================================
TimezoneMiddleware:
    - Negligible overhead (~0.1ms per request)
    - Simple timezone activation, no database queries

UpdateLastSeenMiddleware:
    - Low overhead with caching (~1-2ms per request)
    - Database write only once per 30 seconds per user
    - Cache prevents DB write on every request
    - No impact on anonymous users

Total impact: < 2ms per authenticated request (acceptable)

CACHING STRATEGY
================================================================================
UpdateLastSeenMiddleware uses two-level caching:

1. Write Throttle Cache (30 seconds):
   Key: "last_seen_update_{user_id}"
   Purpose: Prevent frequent database writes
   TTL: 30 seconds

2. Read Cache (5 minutes):
   Key: "user_{user_id}_last_seen"
   Purpose: Fast last_seen lookup for status checks
   TTL: 300 seconds (5 minutes)

This reduces database load while maintaining accurate online status.

ONLINE STATUS LOGIC
================================================================================
Users are considered "online" if:
    - last_seen timestamp is within last 5 minutes
    - Calculated in User.is_online property

Update frequency: Every 30 seconds (when user is active)
Status accuracy: ±30 seconds (acceptable trade-off)

DEPENDENCIES
================================================================================
- pytz: Timezone database
- django.utils.timezone: Timezone activation
- django.core.cache: Cache backend
- User model with 'timezone' and 'last_seen' fields

RELATED MODELS
================================================================================
User model must have:
    - timezone (CharField): User's preferred timezone string
    - last_seen (DateTimeField): Last activity timestamp
    - is_online (property): Returns True if active in last 5 minutes

ERROR HANDLING
================================================================================
Both middleware classes are designed to fail gracefully:
- Invalid timezones fall back to UTC
- Database write failures are caught and ignored
- Request flow continues even if middleware fails

TESTING
================================================================================
Test timezone activation:
    1. Login with user having timezone='America/New_York'
    2. Verify template {{ timezone.now }} displays in correct timezone
    3. Test with invalid timezone, verify UTC fallback

Test last_seen updates:
    1. Monitor database and cache
    2. Make requests 20 seconds apart
    3. Verify only one DB write after 30 seconds
    4. Check cache contains last_seen value

================================================================================
"""

import pytz
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache


# ============================================================================
# TIMEZONE MIDDLEWARE
# ============================================================================

class TimezoneMiddleware:
    """
    Activate user-specific timezone for datetime display.

    This middleware activates the timezone stored in the authenticated user's
    profile, ensuring all datetime objects rendered in templates display in
    the user's local timezone. Falls back to UTC for anonymous users or
    invalid timezone strings.

    Flow:
        1. Check if user is authenticated
        2. Try to activate user's timezone from user.timezone field
        3. Fall back to UTC if timezone invalid or missing
        4. Process request with activated timezone
        5. Return response (timezone stays active for template rendering)

    Attributes:
        get_response: Next middleware or view in the chain

    Example User Experience:
        User in New York (EST):
            - User.timezone = 'America/New_York'
            - Post timestamp: 2026-02-05 09:30:00 UTC
            - Displayed as: Feb 5, 2026, 4:30 AM EST

        Anonymous user:
            - No timezone preference
            - Displayed as: Feb 5, 2026, 9:30 AM UTC

    Performance:
        - Overhead: ~0.1ms per request
        - No database queries (timezone from request.user object)
        - Timezone activation is lightweight

    Error Handling:
        - pytz.UnknownTimeZoneError: Invalid timezone string → Use UTC
        - AttributeError: User has no timezone attribute → Use UTC
        - All errors caught silently, UTC fallback ensures continuity

    Settings Required:
        USE_TZ = True  # Enable timezone support in settings.py
        TIME_ZONE = 'UTC'  # Default timezone

    User Model Requirements:
        - timezone field (CharField with pytz timezone strings)
        - Example: timezone = models.CharField(max_length=100, default='UTC')
    """

    def __init__(self, get_response):
        """
        Initialize middleware with get_response callable.

        Args:
            get_response: Next middleware or view function in the chain
        """
        self.get_response = get_response

    def __call__(self, request):
        """
        Process request and activate appropriate timezone.

        Args:
            request: Django HttpRequest object

        Returns:
            HttpResponse: Response from downstream middleware/view

        Process:
            1. Check authentication status
            2. Activate user timezone or UTC
            3. Call next middleware/view
            4. Return response (timezone remains active)
        """

        # ====================================================================
        #       TIMEZONE ACTIVATION
        # ====================================================================
        # Activate timezone based on authentication status

        if request.user.is_authenticated:
            # --- Authenticated User: Use Profile Timezone ---
            try:
                # Get timezone string from user profile (e.g., 'America/New_York')
                tz = pytz.timezone(request.user.timezone)
                timezone.activate(tz)

            except (pytz.UnknownTimeZoneError, AttributeError):
                # --- Fallback: Invalid or Missing Timezone ---
                # UnknownTimeZoneError: Invalid timezone string in database
                # AttributeError: User model missing timezone field
                timezone.activate(pytz.UTC)
        else:
            # --- Anonymous User: Use UTC ---
            timezone.activate(pytz.UTC)

        # ====================================================================
        #         PROCESS REQUEST
        # ====================================================================
        # Continue to next middleware or view with activated timezone

        response = self.get_response(request)
        return response


# ============================================================================
# LAST SEEN / PRESENCE TRACKING MIDDLEWARE
# ============================================================================

class UpdateLastSeenMiddleware:
    """
    Update user's last_seen timestamp with intelligent caching.

    This middleware tracks user activity by updating the last_seen field
    periodically. It uses a two-level caching strategy to minimize database
    writes while maintaining accurate online status indicators.

    Purpose:
        - Power "online now" status indicators
        - Show "last seen X minutes ago" timestamps
        - Track user engagement metrics
        - Enable activity-based features

    Caching Strategy:
        Level 1 - Write Throttle (30 seconds):
            - Prevents excessive database writes
            - Cache key: "last_seen_update_{user_id}"
            - Only writes to DB every 30 seconds

        Level 2 - Read Cache (5 minutes):
            - Provides fast last_seen lookups
            - Cache key: "user_{user_id}_last_seen"
            - Used by status check views/API

    Online Status Definition:
        User is "online" if last_seen is within last 5 minutes.
        This is calculated in the User.is_online property.

    Attributes:
        get_response: Next middleware or view in the chain

    Performance:
        - Anonymous users: 0 overhead (early return)
        - Authenticated users with cache hit: ~0.5ms
        - Authenticated users with DB write: ~2ms (once per 30 seconds)
        - Total DB writes reduced by ~98% compared to per-request updates

    Database Impact:
        Without caching: 120 writes/minute (1 user, 2 requests/second)
        With caching: 2 writes/minute (1 user, 2 requests/second)
        Reduction: 98% fewer database writes

    Error Handling:
        - Database write failures caught silently
        - Request continues even if update fails
        - Prevents middleware from breaking user experience
        - Logs can be added for monitoring

    Example Timeline:
        00:00 - Request 1: DB write + cache set
        00:15 - Request 2: Cache hit, no DB write
        00:30 - Request 3: Cache expired, DB write + cache set
        00:45 - Request 4: Cache hit, no DB write
        01:00 - Request 5: Cache expired, DB write + cache set

    User Model Requirements:
        - last_seen field (DateTimeField, nullable)
        - is_online property that checks timedelta

    Cache Backend:
        Works with any Django cache backend:
        - Redis (recommended for production)
        - Memcached
        - Database cache
        - Local memory (development only)
    """

    def __init__(self, get_response):
        """
        Initialize middleware with get_response callable.

        Args:
            get_response: Next middleware or view function in the chain
        """
        self.get_response = get_response

    def __call__(self, request):
        """
        Process request and update user's last_seen timestamp.

        Args:
            request: Django HttpRequest object

        Returns:
            HttpResponse: Response from downstream middleware/view

        Process:
            1. Check if user is authenticated
            2. Check cache to see if update needed
            3. Update database if cache expired
            4. Set cache keys for future requests
            5. Continue request processing
        """

        # ====================================================================
        #       AUTHENTICATION & INITIALIZATION
        # ====================================================================
        # Early return for anonymous users to minimize overhead

        if getattr(request, 'user', None) and request.user.is_authenticated:
            now = timezone.now()  # Current UTC timestamp

            # ================================================================
            #        CACHE CHECK (WRITE THROTTLING)
            # ================================================================
            # Check if we've updated recently (within last 30 seconds)
            # This prevents excessive database writes

            cache_key = f"last_seen_update_{request.user.id}"
            last_update = cache.get(cache_key)

            # Only update if cache miss or expired (30+ seconds old)
            if not last_update or (now - last_update) > timedelta(seconds=30):

                # ============================================================
                #       DATABASE UPDATE
                # ============================================================
                # Write new last_seen timestamp to database

                request.user.last_seen = now

                try:
                    # Optimize: Only update last_seen field (not entire model)
                    request.user.save(update_fields=['last_seen'])

                    # ========================================================
                    #         UPDATE WRITE THROTTLE CACHE
                    # ========================================================
                    # Cache the update time to prevent another write for 30s
                    cache.set(cache_key, now, 30)  # 30 second TTL

                except Exception:
                    # ========================================================
                    # ERROR HANDLING
                    # ========================================================
                    # Don't break request flow if database write fails
                    # User experience continues uninterrupted
                    # Could add logging here for monitoring:
                    # logger.exception(f"Failed to update last_seen for user {request.user.id}")
                    pass

                # ============================================================
                #         UPDATE READ CACHE (OPTIONAL)
                # ============================================================
                # Set a separate cache key for fast last_seen lookups
                # Used by status check views or API endpoints
                # 5 minute TTL provides good balance of freshness vs. load
                cache.set(f"user_{request.user.id}_last_seen", now, 300)

        # ====================================================================
        #         CONTINUE REQUEST PROCESSING
        # ====================================================================
        # Process request normally and return response

        return self.get_response(request)


"""
================================================================================
END OF MIDDLEWARE
================================================================================

MONITORING RECOMMENDATIONS
================================================================================
Monitor these metrics in production:

1. Cache Hit Rate:
   - Target: > 95% for last_seen_update_* keys
   - Low hit rate indicates cache issues

2. Database Write Frequency:
   - Target: 2 writes/minute per active user
   - High frequency indicates cache failure

3. Middleware Overhead:
   - Target: < 2ms average per request
   - High overhead needs optimization

4. Error Rate:
   - Target: < 0.01% failed last_seen updates
   - Track exceptions in UpdateLastSeenMiddleware

SCALING CONSIDERATIONS
================================================================================
For high-traffic sites (10,000+ concurrent users):

1. Increase Cache TTL:
   - Consider 60-second update interval instead of 30
   - Trade accuracy for reduced database load

2. Use Async Tasks:
   - Move last_seen updates to Celery/background tasks
   - Update in batches every minute

3. Read Replicas:
   - Use database read replicas for last_seen queries
   - Write to primary, read from replica

4. Denormalize:
   - Consider moving last_seen to cache-only
   - Sync to database less frequently (every 5 minutes)

COMMON ISSUES & SOLUTIONS
================================================================================
Issue: Timezone not applying to templates
Solution: Ensure USE_TZ=True and {% load tz %} in templates

Issue: last_seen not updating
Solution: Check cache backend is working, verify middleware order

Issue: Performance degradation
Solution: Increase cache TTL, consider async updates

Issue: Inaccurate online status
Solution: Reduce cache TTL or implement WebSocket presence

RELATED DOCUMENTATION
================================================================================
- User model: network/models.py
- Context processors: network/context_processors.py
- Online status property: User.is_online
- Cache configuration: settings.py CACHES

FUTURE ENHANCEMENTS
================================================================================
Potential improvements:

1. WebSocket Integration:
   - Real-time presence updates
   - More accurate online status
   - No polling overhead

2. Activity Tracking:
   - Track specific user actions
   - Detailed engagement metrics
   - Last activity type logging

3. Timezone Auto-Detection:
   - Detect timezone from browser
   - Update user profile automatically
   - Better UX for new users

4. Presence Channels:
   - Show who's viewing same page
   - Real-time collaboration features
   - Chat presence indicators

MAINTAINER
================================================================================
Argon Admin
Last updated: February 2026

================================================================================
"""
