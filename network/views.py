"""
network/views.py

Professional Django views for Argon Network application(Production ready app based on the foundation of Harvarx CS50W Project 4)
This file contains all view functions organized nicely.

Version: 2.0 (Production Ready)
Last Updated: February 2026

Structure:
    1. Imports & Constants
    2. Helper Functions (Private utilities)
    3. Authentication & Account Management
    4. User Profile & Settings
    5. Posts & Content Management
    6. Social Features (Follow/Block/Privacy)
    7. Comments & Interactions
    8. Notifications
    9. Messaging System (DM & Groups)
    10. Group Management
    11. API Endpoints
"""

# ============================================================================
# IMPORTS & CONFIGURATION
# ============================================================================

import os
import re
import json
import logging
from datetime import datetime, timedelta

import pytz
import requests

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives, send_mail
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q, Count
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    HttpResponseForbidden,
    JsonResponse
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.html import strip_tags
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods



from .models import (
    User,
    Post,
    PostMedia,
    Follow,
    Notification,
    Message,
    Comment,
    Block,
    PrivacySettings,
    Conversation,
    ConversationMember
)

# Logger configuration
logger = logging.getLogger(__name__)

# Constants
MENTION_RE = re.compile(r'(?<!\w)@([A-Za-z0-9_\.]{1,30})')
TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.all_timezones]


# ============================================================================
# HELPER FUNCTIONS (Private Utilities)
# ============================================================================

def _zodiac_sign(month: int, day: int) -> str:
    """
    Calculate western zodiac sign from birth month and day.

    Args:
        month: Month as integer (1-12)
        day: Day as integer (1-31)

    Returns:
        String name of zodiac sign
    """
    if (month == 3 and day >= 21) or (month == 4 and day <= 19):
        return "Aries"
    if (month == 4 and day >= 20) or (month == 5 and day <= 20):
        return "Taurus"
    if (month == 5 and day >= 21) or (month == 6 and day <= 20):
        return "Gemini"
    if (month == 6 and day >= 21) or (month == 7 and day <= 22):
        return "Cancer"
    if (month == 7 and day >= 23) or (month == 8 and day <= 22):
        return "Leo"
    if (month == 8 and day >= 23) or (month == 9 and day <= 22):
        return "Virgo"
    if (month == 9 and day >= 23) or (month == 10 and day <= 22):
        return "Libra"
    if (month == 10 and day >= 23) or (month == 11 and day <= 21):
        return "Scorpio"
    if (month == 11 and day >= 22) or (month == 12 and day <= 21):
        return "Sagittarius"
    if (month == 12 and day >= 22) or (month == 1 and day <= 19):
        return "Capricorn"
    if (month == 1 and day >= 20) or (month == 2 and day <= 18):
        return "Aquarius"
    return "Pisces"


def _birth_context_for(user):
    """
    Generate birthdate context dictionary for template rendering.

    Args:
        user: User object

    Returns:
        Dictionary with birth_zodiac, birth_month, birth_day, birth_year
    """
    bd = getattr(user, "birth_date", None)
    if not bd:
        return {
            "birth_zodiac": "",
            "birth_month": "",
            "birth_day": "",
            "birth_year": ""
        }
    return {
        "birth_zodiac": _zodiac_sign(bd.month, bd.day),
        "birth_month": bd.month,
        "birth_day": bd.day,
        "birth_year": bd.year
    }


def _extract_mentions(text):
    """
    Extract @username mentions from text using regex.

    Args:
        text: String content to parse

    Returns:
        Set of usernames (without @ symbol)
    """
    if not text:
        return set()
    return set(m.group(1) for m in MENTION_RE.finditer(text))


def _blocked_user_ids_for(user):
    """
    Get all user IDs that should be hidden due to blocking (bidirectional).

    Args:
        user: User object

    Returns:
        Set of user IDs blocked by or blocking the user
    """
    if not user or not user.is_authenticated:
        return set()

    blocked_by_me = Block.objects.filter(blocker=user).values_list('blocked_id', flat=True)
    blocked_me = Block.objects.filter(blocked=user).values_list('blocker_id', flat=True)
    return set(blocked_by_me) | set(blocked_me)


def _notify_mentions_in_post(actor, post, text, context_label):
    """
    Create notifications for users mentioned in post/comment content.

    Args:
        actor: User who created the mention
        post: Post object for the notification
        text: Content containing mentions
        context_label: String describing context ('post' or 'comment')
    """
    mentioned = _extract_mentions(text)
    if not mentioned:
        return

    blocked_ids = _blocked_user_ids_for(actor)

    q = Q()
    for uname in mentioned:
        q |= Q(username__iexact=uname)

    qs = User.objects.filter(q).exclude(id=actor.id)
    if blocked_ids:
        qs = qs.exclude(id__in=blocked_ids)

    for u in qs.distinct():
        Notification.objects.create(
            user=u,
            actor=actor,
            verb=f"mentioned you in a {context_label}",
            post=post
        )


def _notify_mentions_in_group_message(actor, conversation, text):
    """
    Create notifications for users mentioned in group chat messages.

    Args:
        actor: User who sent the message
        conversation: Conversation object
        text: Message content
    """
    mentioned = _extract_mentions(text)
    if not mentioned:
        return

    blocked_ids = _blocked_user_ids_for(actor)
    member_ids = ConversationMember.objects.filter(
        conversation=conversation
    ).values_list('user_id', flat=True)

    q = Q()
    for uname in mentioned:
        q |= Q(username__iexact=uname)

    qs = User.objects.filter(q, id__in=member_ids).exclude(id=actor.id)
    if blocked_ids:
        qs = qs.exclude(id__in=blocked_ids)

    for u in qs.distinct():
        Notification.objects.create(
            user=u,
            actor=actor,
            verb="mentioned you in group chat",
            post=None,
            conversation=conversation
        )


def _group_admin_group_name(conversation_id):
    """Generate legacy Django Group name for conversation admins."""
    return f"conv_{conversation_id}_admins"


def _get_group_admin_ids(conversation):
    """
    Get set of admin user IDs for a group conversation.
    Checks both ConversationMember.is_admin and legacy Group model.

    Args:
        conversation: Conversation object

    Returns:
        Set of admin user IDs
    """
    if not conversation or not getattr(conversation, "id", None):
        return set()

    admin_ids = set()

    # Primary source: ConversationMember.is_admin field
    try:
        admin_ids.update(
            ConversationMember.objects.filter(
                conversation=conversation,
                is_admin=True
            ).values_list("user_id", flat=True)
        )
    except Exception:
        logger.exception("Error fetching ConversationMember admins for conv %s",
                        getattr(conversation, "id", None))

    # Legacy source: Django Group model (backwards compatibility)
    try:
        gname = _group_admin_group_name(conversation.id)
        grp = Group.objects.filter(name=gname).first()
        if grp:
            admin_ids.update(grp.user_set.values_list("id", flat=True))
    except Exception:
        logger.exception("Error fetching legacy Group admins for conv %s",
                        getattr(conversation, "id", None))

    return admin_ids


def _is_group_admin(user, conversation):
    """Check if user is admin of a group conversation."""
    if not user or not user.is_authenticated:
        return False
    if conversation.created_by_id == user.id:
        return True
    return user.id in _get_group_admin_ids(conversation)


def _set_group_admin(conversation, user, is_admin=True):
    """
    Set or unset group admin status for a user.
    Creator cannot be demoted.

    Args:
        conversation: Conversation object
        user: User to promote/demote
        is_admin: Boolean admin status

    Returns:
        Boolean success status
    """
    if not conversation or not getattr(conversation, 'id', None):
        return False
    if not user or not getattr(user, 'id', None):
        return False

    # Creator is always admin
    if conversation.created_by_id == user.id:
        return True

    member, _ = ConversationMember.objects.get_or_create(
        conversation=conversation,
        user=user
    )
    desired = bool(is_admin)
    if member.is_admin != desired:
        member.is_admin = desired
        member.save(update_fields=['is_admin'])

    # Sync legacy Group model
    try:
        gname = _group_admin_group_name(conversation.id)
        grp, _ = Group.objects.get_or_create(name=gname)
        if desired:
            grp.user_set.add(user)
        else:
            grp.user_set.remove(user)
    except Exception:
        logger.exception("Failed to sync legacy Group for conv %s", conversation.id)

    return True


def user_can_manage(conversation, user):
    """
    Check if user can manage conversation settings and members.

    Args:
        conversation: Conversation object
        user: User to check

    Returns:
        Boolean permission status
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if conversation.created_by_id == user.id:
        return True
    return user.id in _get_group_admin_ids(conversation)


def _get_or_create_dm_conversation(user_a, user_b):
    """
    Find or create a 1:1 conversation between two users.
    FIXED: More reliable query logic to prevent duplicate conversations.
    
    Args:
        user_a: First user
        user_b: Second user
    
    Returns:
        Conversation object
    """
    
    user_a_conv_ids = set(
        ConversationMember.objects
        .filter(user=user_a, conversation__is_group=False)
        .values_list('conversation_id', flat=True)
    )
    
    user_b_conv_ids = set(
        ConversationMember.objects
        .filter(user=user_b, conversation__is_group=False)
        .values_list('conversation_id', flat=True)
    )
    
    common_conv_ids = user_a_conv_ids & user_b_conv_ids
    
    for conv_id in common_conv_ids:
        conv = Conversation.objects.get(id=conv_id)
        member_count = ConversationMember.objects.filter(conversation=conv).count()
        if member_count == 2:
            return conv  
    
    conv = Conversation.objects.create(is_group=False)
    ConversationMember.objects.bulk_create([
        ConversationMember(conversation=conv, user=user_a),
        ConversationMember(conversation=conv, user=user_b),
    ])
    return conv


def _attach_legacy_dm_messages_to_conversation(conv, user_a, user_b):
    """
    Migrate legacy DM messages to conversation model.

    Args:
        conv: Conversation to attach messages to
        user_a: First user
        user_b: Second user
    """
    Message.objects.filter(
        conversation__isnull=True
    ).filter(
        Q(sender=user_a, recipient=user_b) | Q(sender=user_b, recipient=user_a)
    ).update(conversation=conv)


# ============================================================================
# AUTHENTICATION & ACCOUNT MANAGEMENT
# ============================================================================

def index(request):
    """Landing page - redirects authenticated users to feed."""
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('all_posts'))
    return render(request, "network/landing.html")


def login_view(request):
    """
    User login with username or email support.
    Validates credentials and handles inactive accounts.
    """
    if request.method == "POST":
        identifier = request.POST.get("identifier", "").strip()
        password = request.POST.get("password", "")

        # Try to find user by username or email
        user = None
        try:
            user = User.objects.get(username=identifier)
        except User.DoesNotExist:
            try:
                users = User.objects.filter(email__iexact=identifier)
                if users.count() == 1:
                    user = users.first()
                elif users.count() > 1:
                    messages.error(request, "Multiple accounts found with this email. Please use username instead.")
                    return render(request, "network/login.html")
            except User.DoesNotExist:
                pass

        if user:
            user = authenticate(request, username=user.username, password=password)
            if user is not None:
                if user.is_active:
                    login(request, user)
                    messages.success(request, "Login successful! Welcome back.")
                    return redirect('all_posts')
                messages.error(request, "Account is inactive. Please check your email to activate.")
            else:
                messages.error(request, "Invalid password.")
        else:
            messages.error(request, "No account found with that username or email.")

    return render(request, "network/login.html")


def logout_view(request):
    """User logout."""
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirmation = request.POST.get("confirmation", "")

        errors = []

        if not username:
            errors.append("Username is required.")
        elif len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        elif len(username) > 30:
            errors.append("Username cannot exceed 30 characters.")
        elif not username.replace('_', '').isalnum():
            errors.append("Username can only contain letters, numbers, and underscores.")

        if not email:
            errors.append("Email is required.")
        elif '@' not in email or '.' not in email.split('@')[-1]:
            errors.append("Please enter a valid email address.")

        if not password:
            errors.append("Password is required.")
        elif len(password) < 8:
            errors.append("Password must be at least 8 characters.")

        if password != confirmation:
            errors.append("Passwords do not match.")

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, "network/register.html")

        try:
            if User.objects.filter(username=username).exists():
                messages.error(request, "Username already taken.")
                return render(request, "network/register.html")

            if User.objects.filter(email=email).exists():
                messages.error(request, "Email already registered.")
                return render(request, "network/register.html")

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            user.is_active = False
            user.activation_token = get_random_string(32)
            user.save()

            try:
                activation_link = request.build_absolute_uri(
                    reverse('activate', kwargs={'token': user.activation_token})
                )
            except Exception:
                activation_link = f"{request.scheme}://{request.get_host()}/activate/{user.activation_token}/"

            context = {
                'username': username,
                'activation_link': activation_link,
                'email': email,
                'protocol': 'https' if request.is_secure() else 'http',
                'domain': request.get_host(),
                'unsubscribe_link': request.build_absolute_uri(reverse('index')),
                'support_email': settings.DEFAULT_FROM_EMAIL or 'support@argonnetwork.com',
                'current_year': datetime.now().year,
                'site_name': 'Argon Network',
            }

            try:
                html_message = render_to_string('network/emails/activation_email.html', context)
                plain_message = strip_tags(html_message)
            except Exception as template_error:
                logger.warning(f"Template render failed, using fallback: {template_error}")
                html_message = f"""
                <h2>Welcome to Argon Network, {username}!</h2>
                <p>Click below to activate:</p>
                <p><a href="{activation_link}">Activate Account</a></p>
                <p>Or copy: {activation_link}</p>
                """
                plain_message = f"Welcome! Activate: {activation_link}"

            try:
                email_msg = EmailMultiAlternatives(
                    subject=f'Activate Your Argon Network Account - {username}',
                    body=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                    reply_to=[settings.DEFAULT_FROM_EMAIL],
                    headers={
                        'X-Priority': '1',
                        'X-Mailer': 'Django',
                        'Precedence': 'bulk',
                        'List-Unsubscribe': f'<mailto:{settings.DEFAULT_FROM_EMAIL}?subject=unsubscribe>',
                        'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
                        'X-Entity-Ref-ID': str(user.id),
                    }
                )
                email_msg.attach_alternative(html_message, "text/html")
                email_msg.send(fail_silently=False)

                logger.info(f"Registration success for {email}. Activation email sent.")
                messages.success(
                    request,
                    "Registration successful! Check your email (including spam) for activation link."
                )
                return render(request, "network/register.html")

            except Exception as email_error:
                user.delete()
                logger.error(f"Email send failed for {email}: {str(email_error)}")
                messages.error(
                    request,
                    "Failed to send activation email. Please try again later."
                )
                return render(request, "network/register.html")

        except IntegrityError as e:
            logger.warning(f"IntegrityError during registration: {str(e)}")
            messages.error(request, "Username or email already taken.")
            return render(request, "network/register.html")

        except Exception as e:
            logger.error(f"Unexpected registration error for {email}: {str(e)}", exc_info=True)
            messages.error(
                request,
                "An unexpected error occurred. Please try again later."
            )
            return render(request, "network/register.html")

    return render(request, "network/register.html") 



def activate(request, token):
    """
    Email activation endpoint.
    Activates user account via emailed token.
    """
    try:
        user = User.objects.get(activation_token=token, is_active=False)
        user.is_active = True
        user.activation_token = ''
        user.save()
        login(request, user)
        messages.success(request, "Account activated successfully! Welcome to Argon Network.")
        return redirect('index')
    except User.DoesNotExist:
        messages.error(request, "Invalid or expired activation link.")
        return render(request, "network/activation_error.html")


# ============================================================================
# USER PROFILE & SETTINGS
# ============================================================================

@login_required
def profile(request, username):
    """
    User profile page with posts, followers, and privacy-aware content.
    Respects blocking and privacy settings.
    """
    profile_user = get_object_or_404(User, username=username)

    # Check block status
    is_blocked = False
    has_blocked_me = False
    try:
        is_blocked = Block.objects.filter(blocker=request.user, blocked=profile_user).exists()
        has_blocked_me = Block.objects.filter(blocker=profile_user, blocked=request.user).exists()
    except (Block.DoesNotExist, AttributeError):
        pass

    # Determine interaction permissions
    can_follow = not (is_blocked or has_blocked_me) and request.user != profile_user
    can_message = not (is_blocked or has_blocked_me) and request.user != profile_user

    # Get privacy settings
    privacy_settings, _ = PrivacySettings.objects.get_or_create(
        user=profile_user,
        defaults={"post_visibility": "universal"}
    )

    # Determine if viewer can see posts
    allowed_to_see_posts = True

    if request.user != profile_user:
        if is_blocked or has_blocked_me:
            allowed_to_see_posts = False
        else:
            visibility = privacy_settings.post_visibility

            if visibility == "universal":
                allowed_to_see_posts = True
            elif visibility == "followers":
                allowed_to_see_posts = profile_user.followers.filter(
                    follower=request.user
                ).exists()
            elif visibility == "following":
                allowed_to_see_posts = profile_user.following.filter(
                    followed=request.user
                ).exists()
            elif visibility == "both":
                allowed_to_see_posts = (
                    profile_user.followers.filter(follower=request.user).exists()
                    and profile_user.following.filter(followed=request.user).exists()
                )
            else:
                allowed_to_see_posts = False

    # Build posts queryset
    if allowed_to_see_posts:
        posts_qs = (
            profile_user.posts
            .select_related("user")
            .prefetch_related("media", "thumbs_up", "thumbs_down", "comments__user")
            .order_by("-timestamp")
        )
    else:
        posts_qs = Post.objects.none()

    # Attach root comments
    for post in posts_qs:
        post.root_comments = post.comments.filter(parent__isnull=True).order_by("timestamp")

    # Paginate
    paginator = Paginator(posts_qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Follow status
    is_following = False
    if request.user != profile_user:
        is_following = Follow.objects.filter(
            follower=request.user,
            followed=profile_user
        ).exists()

    return render(request, "network/profile.html", {
        "profile_user": profile_user,
        "page_obj": page_obj,
        "is_following": is_following,
        "is_blocked": is_blocked,
        "has_blocked_me": has_blocked_me,
        "can_follow": can_follow,
        "can_message": can_message,
        "privacy_settings": privacy_settings,
        "birth": _birth_context_for(profile_user),
        "followers_count": profile_user.followers.count(),
        "following_count": profile_user.following.count()
    })


@login_required
def edit_profile(request):
    """
    Profile editing page.
    Handles username, bio, timezone, gender, and birthdate updates.
    """
    user = request.user

    def _render(message_text=None, level="error"):
        ctx = {
            "timezone_choices": TIMEZONE_CHOICES,
            "user": user,
            "birth": _birth_context_for(user),
            "day_range": list(range(1, 32))
        }
        if message_text:
            if level == "success":
                messages.success(request, message_text)
            else:
                ctx["message"] = message_text
        return render(request, "network/edit_profile.html", ctx)

    if request.method == "POST":
        # Username
        new_username = (request.POST.get("username") or "").strip()
        if new_username and new_username != user.username:
            if User.objects.filter(username__iexact=new_username).exists():
                return _render("Username already taken.")
            user.username = new_username

        # Basic fields
        user.bio = request.POST.get("bio", "")
        user.timezone = request.POST.get("timezone", "UTC")
        user.gender = request.POST.get("gender", "")

        # Birthdate handling
        clear_birth = bool(request.POST.get("clear_birth_date"))
        if clear_birth:
            user.birth_date = None
            user.birth_year_hidden = False
            user.birth_date_hidden = False
        else:
            mode = request.POST.get("birth_date_mode") or "full"
            hide_birth = bool(request.POST.get("birth_date_hidden"))

            if mode == "md":
                # Month/day only
                try:
                    month = int(request.POST.get("birth_month") or 0)
                    day = int(request.POST.get("birth_day") or 0)
                except ValueError:
                    month, day = 0, 0

                if month and day:
                    try:
                        user.birth_date = datetime(2000, month, day).date()
                        user.birth_year_hidden = True
                        user.birth_date_hidden = hide_birth
                    except ValueError:
                        return _render("That day/month combination isn't valid.")
                else:
                    user.birth_date = None
                    user.birth_year_hidden = False
                    user.birth_date_hidden = False
            else:
                # Full date
                date_str = (request.POST.get("birth_date") or "").strip()
                if date_str:
                    try:
                        user.birth_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        user.birth_year_hidden = False
                        user.birth_date_hidden = hide_birth
                    except ValueError:
                        return _render("Please enter a valid date.")
                else:
                    user.birth_date = None
                    user.birth_year_hidden = False
                    user.birth_date_hidden = False

        user.save()
        return redirect("profile", username=user.username)

    return _render()


@csrf_exempt
@login_required
def quick_upload_picture(request):
    """Quick profile picture upload endpoint."""
    if request.method == "POST" and 'profile_picture' in request.FILES:
        request.user.profile_picture = request.FILES['profile_picture']
        request.user.save()
    return HttpResponseRedirect(reverse('profile', args=[request.user.username]))


@login_required
def discover_users(request):
    """User discovery page with search."""
    query = request.GET.get('q', '').strip()
    users = User.objects.exclude(id=request.user.id)

    if query:
        users = users.filter(username__icontains=query)

    # Get block status
    blocked_user_ids = set(Block.objects.filter(
        blocker=request.user
    ).values_list('blocked_id', flat=True))
    blocked_by_user_ids = set(Block.objects.filter(
        blocked=request.user
    ).values_list('blocker_id', flat=True))

    return render(request, "network/discover_users.html", {
        'users': users,
        'query': query,
        'blocked_user_ids': blocked_user_ids,
        'blocked_by_user_ids': blocked_by_user_ids
    })


@login_required
def followers_list(request, username):
    """List of user's followers."""
    profile_user = get_object_or_404(User, username=username)
    followers = User.objects.filter(following__followed=profile_user)

    # Exclude blocked users
    try:
        blocked_user_ids = Block.objects.filter(
            blocker=request.user
        ).values_list('blocked_id', flat=True)
        followers = followers.exclude(id__in=blocked_user_ids)
    except (Block.DoesNotExist, AttributeError):
        pass

    is_following_dict = {
        str(f.id): request.user.following.filter(followed=f).exists() 
        for f in followers
    }

    return render(request, "network/followers_list.html", {
        'profile_user': profile_user,
        'users': followers,
        'list_type': 'Followers',
        'is_following_dict': is_following_dict
    })


@login_required
def following_list(request, username):
    """List of users that this user follows."""
    profile_user = get_object_or_404(User, username=username)
    following = User.objects.filter(followers__follower=profile_user)

    # Exclude blocked users
    try:
        blocked_user_ids = Block.objects.filter(
            blocker=request.user
        ).values_list('blocked_id', flat=True)
        following = following.exclude(id__in=blocked_user_ids)
    except (Block.DoesNotExist, AttributeError):
        pass

    is_following_dict = {
        str(u.id): request.user.following.filter(followed=u).exists() 
        for u in following
    }

    return render(request, "network/followers_list.html", {
        'profile_user': profile_user,
        'users': following,
        'list_type': 'Following',
        'is_following_dict': is_following_dict
    })


# ============================================================================
# POSTS & CONTENT MANAGEMENT
# ============================================================================

@login_required
def all_posts(request):
    """
    Main feed showing all posts with privacy filtering.
    Respects block relationships and post visibility settings.
    """
    base_qs = Post.objects.select_related('user').prefetch_related(
        'media', 'thumbs_up', 'thumbs_down', 'comments__user'
    ).order_by('-timestamp')

    visible_posts = []
    for post in base_qs:
        # Skip blocked users
        try:
            if Block.objects.filter(blocker=request.user, blocked=post.user).exists():
                continue
        except (Block.DoesNotExist, AttributeError):
            pass

        # Check privacy settings
        privacy_settings, _ = PrivacySettings.objects.get_or_create(
            user=post.user,
            defaults={'post_visibility': 'universal'}
        )
        visibility = privacy_settings.post_visibility

        if visibility == 'universal':
            visible_posts.append(post)
        elif visibility == 'followers' and post.user.followers.filter(follower=request.user).exists():
            visible_posts.append(post)
        elif visibility == 'following' and post.user.following.filter(followed=request.user).exists():
            visible_posts.append(post)
        elif visibility == 'both' and (
            post.user.followers.filter(follower=request.user).exists() and
            post.user.following.filter(followed=request.user).exists()
        ): 
            visible_posts.append(post)

    post_ids = [p.id for p in visible_posts]
    posts = Post.objects.filter(id__in=post_ids).order_by('-timestamp').prefetch_related(
        'media', 'thumbs_up', 'thumbs_down', 'comments__user'
    )

    # Attach root comments
    for post in posts:
        post.root_comments = post.comments.filter(parent__isnull=True).order_by('timestamp')

    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "network/all_posts.html", {'page_obj': page_obj})


@login_required
def following(request):
    """Feed showing posts from followed users only."""
    followed_user_ids = request.user.following.values_list('followed_id', flat=True)
    filtered_posts = []

    for post in Post.objects.filter(
        user__id__in=followed_user_ids
    ).select_related('user').prefetch_related('media', 'comments__user'):
        # Skip blocked users
        try:
            if Block.objects.filter(blocker=request.user, blocked=post.user).exists():
                continue
        except (Block.DoesNotExist, AttributeError):
            pass

        # Check privacy
        privacy_settings, _ = PrivacySettings.objects.get_or_create(
            user=post.user,
            defaults={'post_visibility': 'universal'}
        )
        visibility = privacy_settings.post_visibility

        if visibility == 'universal':
            filtered_posts.append(post)
        elif visibility == 'followers' and post.user.followers.filter(follower=request.user).exists():
            filtered_posts.append(post)
        elif visibility == 'following' and post.user.following.filter(followed=request.user).exists():
            filtered_posts.append(post)
        elif visibility == 'both' and (
            post.user.followers.filter(follower=request.user).exists() and
            post.user.following.filter(followed=request.user).exists()
        ):
            filtered_posts.append(post)

    post_ids = [p.id for p in filtered_posts]
    posts = Post.objects.filter(id__in=post_ids).order_by('-timestamp').prefetch_related(
        'media', 'thumbs_up', 'thumbs_down', 'comments__user'
    )

    # Attach root comments
    for post in posts:
        post.root_comments = post.comments.filter(parent__isnull=True).order_by('timestamp')

    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "network/following.html", {'page_obj': page_obj})


@login_required
def post_detail(request, post_id):
    """
    Individual post detail page with comments.
    Respects privacy and block settings.
    """
    post = get_object_or_404(
        Post.objects.select_related('user').prefetch_related(
            'media', 'thumbs_up', 'thumbs_down', 'comments__user', 'comments__parent'
        ),
        id=post_id
    )

    # Check if blocked
    try:
        if Block.objects.filter(blocker=request.user, blocked=post.user).exists():
            messages.error(request, "You cannot view this post.")
            return redirect('all_posts')
    except (Block.DoesNotExist, AttributeError):
        pass

    # Check privacy
    privacy_settings, _ = PrivacySettings.objects.get_or_create(
        user=post.user,
        defaults={'post_visibility': 'universal'}
    )
    visibility = privacy_settings.post_visibility

    allowed = False
    if visibility == 'universal':
        allowed = True
    elif visibility == 'followers' and post.user.followers.filter(follower=request.user).exists():
        allowed = True
    elif visibility == 'following' and post.user.following.filter(followed=request.user).exists():
        allowed = True
    elif visibility == 'both' and (
        post.user.followers.filter(follower=request.user).exists() or
        post.user.following.filter(followed=request.user).exists()
    ):
        allowed = True

    if not allowed and request.user != post.user:
        messages.error(request, "This post is not visible to you.")
        return redirect('all_posts')

    root_comments = post.comments.filter(parent__isnull=True).order_by('timestamp')

    context = {
        'post': post,
        'root_comments': root_comments,
        'up_count': post.thumbs_up.count(),
        'down_count': post.thumbs_down.count(),
        'is_upvoted': request.user in post.thumbs_up.all(),
        'is_downvoted': request.user in post.thumbs_down.all()
    }
    return render(request, "network/post_detail.html", context)

@login_required
def new_post(request):
    """Create new post with optional media."""
    if request.method == "POST":
        try:
            content = request.POST.get('content', '').strip()
            media_files = request.FILES.getlist('media_files')
            
            # Validation 1: Content or media required
            if not content and not media_files:
                return JsonResponse({
                    "error": "Post must contain text or media"
                }, status=400)
            
            # Validation 2: Content length
            if len(content) > 1000:
                return JsonResponse({
                    "error": "Post content cannot exceed 1000 characters"
                }, status=400)
            
            # Validation 3: File count
            MAX_FILES = 4
            if len(media_files) > MAX_FILES:
                return JsonResponse({
                    "error": f"Maximum {MAX_FILES} files allowed per post"
                }, status=400)
            
            # Validation 4: File size and type
            MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
            for f in media_files:
                if f.size > MAX_FILE_SIZE:
                    file_size_mb = f.size / (1024 * 1024)
                    return JsonResponse({
                        "error": f"File '{f.name}' is {file_size_mb:.1f}MB. Maximum size is 10MB"
                    }, status=400)
                
                if f.content_type.startswith('audio/'):
                    return JsonResponse({
                        "error": "Audio files are not supported"
                    }, status=400)
                
                is_image = f.content_type.startswith('image/')
                is_video = f.content_type.startswith('video/')
                
                if not is_image and not is_video:
                    return JsonResponse({
                        "error": f"File '{f.name}' has unsupported type. Use images or videos only"
                    }, status=400)
            
            # Create the post
            post = Post.objects.create(user=request.user, content=content)
            
            # Handle media files - CloudinaryField handles everything automatically
            try:
                for f in media_files:
                    media_type = 'video' if f.content_type.startswith('video/') else 'image'
                    PostMedia.objects.create(
                        post=post,
                        file=f,
                        media_type=media_type
                    )
            except Exception as upload_error:
                # If upload fails, delete the post and return error
                post.delete()
                print(f"Media upload failed: {upload_error}")
                import traceback
                traceback.print_exc()
                return JsonResponse({
                    "error": f"Failed to upload media. Please try again."
                }, status=500)
            
            # Notify mentions (don't fail post if this breaks)
            try:
                from .utils import _notify_mentions_in_post
                _notify_mentions_in_post(request.user, post, content, "post")
            except Exception as e:
                print(f"Mention notification failed: {e}")
            
            return JsonResponse({
                "message": "Posted successfully!", 
                "post_id": post.id
            }, status=201)
            
        except Exception as e:
            import traceback
            print(f"Error creating post: {e}")
            traceback.print_exc()
            
            return JsonResponse({
                "error": "An error occurred while creating your post. Please try again."
            }, status=500)
    
    return redirect('all_posts')

    
@csrf_exempt
@login_required
def edit_post(request, post_id):
    """Edit post content (owner only)."""
    post = get_object_or_404(Post, id=post_id, user=request.user)
    if request.method == "PUT":
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        post.content = data.get('content', post.content)
        post.save()
        return JsonResponse({"message": "Post updated"})
    return JsonResponse({"error": "PUT request required"}, status=400)


@csrf_exempt
@login_required
def delete_post(request, post_id):
    """Delete post (owner only)."""
    post = get_object_or_404(Post, id=post_id, user=request.user)
    if request.method == "POST":
        post.delete()
        return JsonResponse({"message": "Post deleted"})
    return JsonResponse({"error": "POST required"}, status=400)


@csrf_exempt
@login_required
def toggle_vote(request, post_id):
    """Toggle upvote/downvote on post."""
    post = get_object_or_404(Post, id=post_id)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    value = data.get('value')
    if value not in (1, -1):
        return JsonResponse({"error": "Invalid vote value"}, status=400)

    if value == 1:
        field = post.thumbs_up
        opposite = post.thumbs_down
    else:
        field = post.thumbs_down
        opposite = post.thumbs_up

    # Toggle vote
    if request.user in field.all():
        field.remove(request.user)
    else:
        opposite.remove(request.user)
        field.add(request.user)
        # Notify post author
        if request.user != post.user:
            Notification.objects.create(
                user=post.user,
                actor=request.user,
                verb="voted on your post",
                post=post
            )

    post.refresh_from_db()

    return JsonResponse({
        "up": post.thumbs_up.count(),
        "down": post.thumbs_down.count(),
        "user_up": request.user in post.thumbs_up.all(),
        "user_down": request.user in post.thumbs_down.all()
    })


# ============================================================================
# SOCIAL FEATURES (Follow/Block/Privacy)
# ============================================================================

@csrf_exempt
@login_required
def toggle_follow(request, username):
    """Toggle follow/unfollow for a user."""
    target_user = get_object_or_404(User, username=username)

    if request.user == target_user:
        return JsonResponse({"error": "Cannot follow yourself"}, status=400)

    # Check for blocks
    is_blocked = Block.objects.filter(blocker=request.user, blocked=target_user).exists()
    has_blocked_me = Block.objects.filter(blocker=target_user, blocked=request.user).exists()

    if is_blocked:
        return JsonResponse({
            "error": "You have blocked this user. Unblock them first to follow."
        }, status=403)

    if has_blocked_me:
        return JsonResponse({
            "error": "This user has blocked you. You cannot follow them."
        }, status=403)

    # Toggle follow
    follow, created = Follow.objects.get_or_create(
        follower=request.user,
        followed=target_user
    )

    if not created:
        follow.delete()
        action = "unfollowed"
    else:
        action = "followed"
        Notification.objects.create(
            user=target_user,
            actor=request.user,
            verb="followed you"
        )

    return JsonResponse({
        "action": action,
        "followers": target_user.followers.count(),
        "following": target_user.following.count()
    })


@csrf_exempt
@login_required
def toggle_block(request, username):
    """Toggle block/unblock for a user."""
    target_user = get_object_or_404(User, username=username)

    if request.user == target_user:
        return JsonResponse({"error": "Cannot block yourself"}, status=400)

    block, created = Block.objects.get_or_create(
        blocker=request.user,
        blocked=target_user
    )

    if not created:
        block.delete()
        action = "unblocked"
    else:
        action = "blocked"

    return JsonResponse({"action": action})


@login_required
def unblock_user(request, username):
    """Unblock a user (from privacy settings page)."""
    target_user = get_object_or_404(User, username=username)
    Block.objects.filter(blocker=request.user, blocked=target_user).delete()
    messages.success(request, f"You have unblocked {username}.")
    return redirect('privacy_settings')


@login_required
def privacy_settings(request):
    """
    Privacy settings page.
    Manage post visibility and view blocked users.
    """
    privacy_settings_obj, _ = PrivacySettings.objects.get_or_create(
        user=request.user,
        defaults={'post_visibility': 'universal'}
    )

    if request.method == "POST":
        privacy_settings_obj.post_visibility = request.POST.get(
            'post_visibility',
            'universal'
        )
        privacy_settings_obj.save()
        messages.success(request, "Privacy settings updated.")
        return redirect('privacy_settings')

    # Get blocked users
    try:
        blocked_qs = request.user.blocks.all().order_by('-timestamp')
    except Exception:
        blocked_qs = Block.objects.filter(blocker=request.user).order_by('-timestamp')

    return render(request, "network/privacy_settings.html", {
        'blocked_users': blocked_qs,
        'privacy_settings': privacy_settings_obj,
        'user': request.user
    })


@login_required
def check_interaction(request, username):
    """API endpoint to check if interaction is allowed with a user."""
    target_user = get_object_or_404(User, username=username)

    is_blocked = Block.objects.filter(blocker=request.user, blocked=target_user).exists()
    has_blocked_me = Block.objects.filter(blocker=target_user, blocked=request.user).exists()

    can_interact = not (is_blocked or has_blocked_me)

    return JsonResponse({
        'can_interact': can_interact,
        'message': 'Cannot interact with this user due to block settings.' if not can_interact else ''
    })


# ============================================================================
# COMMENTS & INTERACTIONS
# ============================================================================

@csrf_exempt
@login_required
def add_comment(request, post_id):
    """
    Add comment to a post with media support and depth limiting.
    Maximum reply depth is 1 (root + one reply level).
    """
    post = get_object_or_404(Post, id=post_id)

    if request.method != "POST":
        return redirect("all_posts")

    content = (request.POST.get("content") or "").strip()
    parent_id = request.POST.get("parent_id")

    # Legacy media fields
    legacy_media_url = (request.POST.get("media_url") or "").strip()
    legacy_media_type = (request.POST.get("media_type") or "text").strip().lower()

    # New file upload
    media_file = request.FILES.get("media")

    # Validate content
    if not content and not media_file and not legacy_media_url:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"error": "Comment cannot be empty"}, status=400)
        messages.error(request, "Comment cannot be empty.")
        return redirect("all_posts")

    # Check parent and depth
    parent = None
    if parent_id:
        try:
            parent = Comment.objects.get(id=parent_id, post=post)

            # Calculate depth
            depth = 0
            current = parent
            while current.parent:
                depth += 1
                current = current.parent

            if depth >= 1:
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse(
                        {"error": "Maximum reply depth reached"},
                        status=400
                    )
                messages.error(request, "Maximum reply depth reached.")
                return redirect("all_posts")
        except Comment.DoesNotExist:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"error": "Invalid parent comment"}, status=400)
            messages.error(request, "Invalid parent comment.")
            return redirect("all_posts")

    # Handle media
    final_media_url = ""
    final_media_type = "text"

    if media_file:
        ctype = media_file.content_type or ""
        final_media_type = 'video' if ctype.startswith("video/") else 'image'
    elif legacy_media_url:
        final_media_url = legacy_media_url
        if legacy_media_type in ("image", "video", "gif", "sticker"):
            final_media_type = legacy_media_type
        else:
            final_media_type = "image"

    # Create comment
    comment = Comment.objects.create(
        post=post,
        user=request.user,
        content=content,
        parent=parent,
        media_url=final_media_url,
        media_type=final_media_type
    )

    # Attach uploaded file
    if media_file:
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        if media_file.size > MAX_FILE_SIZE:
            comment.delete()
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"error": f"File too large. Maximum size is 10MB."},
                    status=400
                )
            messages.error(request, "File too large. Maximum size is 10MB.")
            return redirect("all_posts")
        comment.media = media_file
        comment.media_type = final_media_type
        comment.save(update_fields=["media", "media_type"])

    # Notifications
    _notify_mentions_in_post(request.user, post, content, "comment")
    if post.user != request.user:
        Notification.objects.create(
            user=post.user,
            actor=request.user,
            verb="commented on your post",
            post=post
        )

    # AJAX response
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "status": "success",
            "comment_id": comment.id,
            "user": comment.user.username,
            "avatar": (
                comment.user.profile_picture.url
                if comment.user.profile_picture
                else "/static/default-avatar.png"
            ),
            "content": comment.content,
            "media_url": comment.media.url if comment.media else comment.media_url,
            "media_type": comment.media_type,
            "timestamp": comment.timestamp.strftime("%b %d, %Y • %I:%M %p"),
            "parent_id": parent_id or None
        })

    messages.success(request, "Comment added!")
    return redirect("all_posts")


@csrf_exempt
@login_required
def edit_comment(request, comment_id):
    """Edit comment content (owner only)."""
    if request.method == "PUT":
        try:
            comment = Comment.objects.get(id=comment_id, user=request.user)
            data = json.loads(request.body)
            new_content = data.get('content', '').strip()
            if not new_content:
                return JsonResponse({"error": "Content cannot be empty"}, status=400)
            comment.content = new_content
            comment.save()
            return JsonResponse({"message": "Comment updated", "content": new_content})
        except Comment.DoesNotExist:
            return JsonResponse({"error": "Comment not found or not yours"}, status=404)
    return JsonResponse({"error": "PUT required"}, status=400)


@csrf_exempt
@login_required
def delete_comment(request, comment_id):
    """Delete comment (owner only)."""
    if request.method == "POST":
        try:
            comment = Comment.objects.get(id=comment_id, user=request.user)
            comment.delete()
            return JsonResponse({"status": "success", "message": "Comment deleted"})
        except Comment.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "message": "Not found or not yours"
            }, status=403)
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


# ============================================================================
# NOTIFICATIONS
# ============================================================================

@login_required
def notifications_view(request):
    """Display user notifications and mark as read."""
    notifs = request.user.notifications.all()[:30]
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return render(request, "network/notifications.html", {'notifications': notifs})


@csrf_exempt
@login_required
def mark_notifications_read(request):
    """Mark all notifications as read."""
    if request.method == "POST":
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({"status": "success"})
    return JsonResponse({"error": "POST required"}, status=400)


@login_required
@require_POST
def mark_all_notifications_read(request):
    """Mark all notifications as read."""
    request.user.notifications.all().update(is_read=True)
    return JsonResponse({'success': True, 'message': 'All notifications marked as read.'})


@login_required
@require_POST
def clear_all_notifications(request):
    """Delete all notifications for current user."""
    request.user.notifications.all().delete()
    return JsonResponse({'success': True, 'message': 'All notifications cleared.'})


@login_required
@require_POST
def delete_notification(request, notification_id):
    """Delete a specific notification."""
    try:
        notification = request.user.notifications.get(id=notification_id)
        notification.delete()
        return JsonResponse({'success': True, 'message': 'Notification deleted.'})
    except Notification.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Notification not found.'
        }, status=404)


# ============================================================================
# MESSAGING SYSTEM (DM & Groups)
# ============================================================================

@login_required
def messages_inbox(request):
    """
    Messages inbox showing all conversations (DM and group).
    Performs lazy migration of legacy DM messages to conversation model.
    """
    # Migrate legacy DMs
    legacy_sent = request.user.sent_messages.filter(
        conversation__isnull=True
    ).values_list('recipient_id', flat=True).distinct()
    legacy_received = request.user.received_messages.filter(
        conversation__isnull=True
    ).values_list('sender_id', flat=True).distinct()
    legacy_user_ids = set(list(legacy_sent) + list(legacy_received))

    if legacy_user_ids:
        for uid in legacy_user_ids:
            try:
                other_user = User.objects.get(id=uid)
            except User.DoesNotExist:
                continue
            conv = _get_or_create_dm_conversation(request.user, other_user)
            _attach_legacy_dm_messages_to_conversation(conv, request.user, other_user)

    # Build inbox
    memberships = (
        ConversationMember.objects
        .filter(user=request.user)
        .select_related('conversation')
    )

    conversations = []
    for mem in memberships:
        conv = mem.conversation

        # Skip hidden conversations
        if conv.hidden_by.filter(id=request.user.id).exists():
            continue

        members_qs = User.objects.filter(
            conversation_memberships__conversation=conv
        ).distinct()

        other_user = None
        title = conv.name.strip() if conv.name else ""

        if not conv.is_group:
            other_user = members_qs.exclude(id=request.user.id).first()
            title = other_user.username if other_user else title or "Conversation"
        else:
            title = title or f"Group #{conv.id}"

        latest = conv.messages.order_by('-timestamp').first()

        # Calculate unread count
        if conv.is_group:
            last_read = mem.last_read_at or conv.created_at
            unread = conv.messages.exclude(sender=request.user).filter(
                timestamp__gt=last_read
            ).count()
        else:
            unread = conv.messages.filter(
                sender=other_user,
                recipient=request.user,
                is_read=False
            ).count() if other_user else 0

        conversations.append({
            'conversation': conv,
            'title': title,
            'is_group': conv.is_group,
            'other_user': other_user,
            'latest_message': latest,
            'unread_count': unread
        })

    # Sort by latest message
    conversations.sort(
        key=lambda c: (
            c['latest_message'].timestamp if c['latest_message'] 
            else c['conversation'].created_at
        ),
        reverse=True
    )

    return render(request, "network/messages/messages_inbox.html", {
        'conversations': conversations
    })

@login_required
def conversation(request, username):
    """
    Legacy DM route - redirects to conversation room.
    Checks for blocks before allowing messaging.
    Auto-unhides conversation if user re-initiates contact.
    """
    other_user = get_object_or_404(User, username=username)
    is_blocked = False
    has_blocked_me = False
    try:
        is_blocked = Block.objects.filter(
            blocker=request.user,
            blocked=other_user
        ).exists()
        has_blocked_me = Block.objects.filter(
            blocker=other_user,
            blocked=request.user
        ).exists()
    except (Block.DoesNotExist, AttributeError):
        pass
    if is_blocked or has_blocked_me:
        messages.error(request, "Cannot message this user due to block settings.")
        return redirect('messages_inbox')
    if request.user == other_user:
        return HttpResponseRedirect(reverse('messages_inbox'))
    conv = _get_or_create_dm_conversation(request.user, other_user)
    _attach_legacy_dm_messages_to_conversation(conv, request.user, other_user)
    if conv.hidden_by.filter(id=request.user.id).exists():
        conv.hidden_by.remove(request.user)
        messages.success(request, f"Conversation with {other_user.username} restored.")
    return redirect('conversation_room', conversation_id=conv.id)


@login_required
def conversation_room(request, conversation_id):
    """
    Conversation room for both DM and group chats.
    Handles message sending, read receipts, and online status.
    """
    conversation = get_object_or_404(Conversation, id=conversation_id)

    # Check membership
    if not ConversationMember.objects.filter(
        conversation=conversation,
        user=request.user
    ).exists():
        return HttpResponseForbidden()

    # Assign creator for legacy groups
    if conversation.is_group and conversation.created_by_id is None:
        first_member = (
            ConversationMember.objects
            .filter(conversation=conversation)
            .order_by("joined_at")
            .select_related("user")
            .first()
        )
        if first_member:
            conversation.created_by = first_member.user
            conversation.save(update_fields=["created_by"])

    # Get members
    members_qs = User.objects.filter(
        conversation_memberships__conversation=conversation
    ).distinct()

    other_user = None
    if not conversation.is_group:
        other_user = members_qs.exclude(id=request.user.id).first()

    msgs = Message.objects.filter(conversation=conversation).order_by("timestamp")

    # Online status
    other_user_is_online = False
    other_user_status = None

    if other_user:
        other_user_is_online = other_user.is_online
        other_user_status = "Active now" if other_user_is_online else "Offline"

    # Mark as read
    if conversation.is_group:
        ConversationMember.objects.filter(
            conversation=conversation,
            user=request.user
        ).update(last_read_at=timezone.now())
    else:
        if other_user:
            Message.objects.filter(
                conversation=conversation,
                sender=other_user,
                recipient=request.user,
                is_read=False
            ).update(is_read=True)

    # Handle message sending
    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        media_file = request.FILES.get("media")

        if content or media_file:
            msg = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                recipient=other_user if not conversation.is_group else None,
                content=content or ""
            )

            # Notify mentions in group
            if conversation.is_group and content:
                _notify_mentions_in_group_message(request.user, conversation, content)

            # Handle media
            if media_file:
                content_type = media_file.content_type
                if content_type == "image/gif":
                    media_type = "gif"
                elif content_type.startswith("image/"):
                    media_type = "image"
                elif content_type.startswith("video/"):
                    media_type = "video"
                else:
                    ext = os.path.splitext(media_file.name)[1].lower()
                    if ext == ".gif":
                        media_type = "gif"
                    elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
                        media_type = "image"
                    elif ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
                        media_type = "video"
                    else:
                        media_type = "image"

                msg.media = media_file
                msg.media_type = media_type
                msg.save()

            # Unhide conversation
            conversation.hidden_by.remove(request.user)
            if other_user:
                conversation.hidden_by.remove(other_user)
                request.user.hidden_conversations.remove(other_user)
                other_user.hidden_conversations.remove(request.user)

        return redirect("conversation_room", conversation_id=conversation.id)

    # Get admin IDs and permissions
    admin_ids = set(_get_group_admin_ids(conversation))
    if conversation.created_by_id:
        admin_ids.add(conversation.created_by_id)

    can_manage_members = user_can_manage(conversation, request.user)

    # Calculate read receipts for group messages
    if conversation.is_group:
        last_read_map = {
            uid: last_read_at
            for uid, last_read_at in ConversationMember.objects.filter(
                conversation=conversation
            ).values_list("user_id", "last_read_at")
        }

        for msg in msgs:
            if msg.sender_id == request.user.id:
                seen_names = []
                for u in members_qs:
                    if u.id == request.user.id:
                        continue
                    last_read = last_read_map.get(u.id)
                    if last_read and last_read >= msg.timestamp:
                        seen_names.append(u.username)
                msg.seen_by = seen_names
            else:
                msg.seen_by = []
    else:
        for msg in msgs:
            msg.seen_by = []

    # Get Django messages (for flash messages)
    from django.contrib.messages import get_messages as _get_messages
    messages_django = list(_get_messages(request))

    return render(request, "network/messages/conversation.html", {
        "conversation": conversation,
        "other_user": other_user,
        "other_user_is_online": other_user_is_online,
        "other_user_status": other_user_status,
        "members": members_qs,
        "messages": msgs,
        "admin_ids": admin_ids,
        "can_manage_members": can_manage_members,
        "messages_django": messages_django
    })


@csrf_exempt
@login_required
def delete_message(request, message_id):
    """Delete a message (sender only)."""
    if request.method == "POST":
        try:
            message = Message.objects.get(id=message_id, sender=request.user)
            message.delete()
            return JsonResponse({"message": "Message deleted"})
        except Message.DoesNotExist:
            return JsonResponse({
                "error": "Message not found or not yours"
            }, status=404)
    return JsonResponse({"error": "POST required"}, status=400)


@csrf_exempt
@login_required
def delete_conversation(request, username):
    """Legacy endpoint to hide a DM conversation."""
    other_user = get_object_or_404(User, username=username)
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    conv = _get_or_create_dm_conversation(request.user, other_user)
    conv.hidden_by.add(request.user)
    request.user.hidden_conversations.add(other_user)

    return JsonResponse({"message": "Conversation hidden"})


def delete_room(request, conversation_id):
    """Hide a conversation room for current user."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    conversation = get_object_or_404(Conversation, id=conversation_id)

    # Check membership
    if not ConversationMember.objects.filter(
        conversation=conversation,
        user=request.user
    ).exists():
        return HttpResponseForbidden()

    # Hide for current user only
    conversation.hidden_by.add(request.user)

    return JsonResponse({"message": "Conversation hidden"})


# ============================================================================
# GROUP MANAGEMENT
# ============================================================================

def create_group(request):
    """Create a new group conversation."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    name = (request.POST.get("name") or "").strip()
    raw_users = request.POST.getlist("users")

    # Create group
    conv = Conversation.objects.create(
        name=name,
        is_group=True,
        created_by=request.user
    )

    # Add creator as member and admin
    ConversationMember.objects.get_or_create(conversation=conv, user=request.user)
    _set_group_admin(conv, request.user, True)

    # Handle avatar
    avatar = request.FILES.get("group_avatar")
    if avatar:
        conv.group_avatar = avatar
        conv.save(update_fields=["group_avatar"])

    # Add members
    for token in raw_users:
        token = (token or "").strip()
        if not token:
            continue

        # Try as user ID
        if token.isdigit():
            uid_int = int(token)
            if uid_int == request.user.id:
                continue
            ConversationMember.objects.get_or_create(
                conversation=conv,
                user_id=uid_int
            )
            continue

        # Try as username
        u = User.objects.filter(username__iexact=token).first()
        if u and u.id != request.user.id:
            ConversationMember.objects.get_or_create(conversation=conv, user=u)

    # Set default name if needed
    if not conv.name:
        conv.name = f"Group #{conv.id}"
        conv.save(update_fields=["name"])

    return JsonResponse({"status": "created", "conversation_id": conv.id})


@login_required
@require_POST
def add_to_conversation(request, conversation_id):
    """Add a user to an existing conversation."""
    conversation = get_object_or_404(Conversation, id=conversation_id)

    # Check membership
    if not ConversationMember.objects.filter(
        conversation=conversation,
        user=request.user
    ).exists():
        return HttpResponseForbidden()

    # Check permissions for groups
    if conversation.is_group and not user_can_manage(conversation, request.user):
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({
                "error": "Only a group admin/creator can add members."
            }, status=403)

    user_id = request.POST.get("user_id")
    username = (request.POST.get("username") or "").strip()

    target_user = None
    if user_id:
        try:
            target_user = User.objects.get(id=int(user_id))
        except (User.DoesNotExist, ValueError):
            target_user = None
    elif username:
        target_user = User.objects.filter(username__iexact=username).first()

    if not target_user:
        return JsonResponse({"error": "User not found"}, status=404)

    if target_user.id == request.user.id:
        return JsonResponse({"error": "Cannot add yourself"}, status=400)

    ConversationMember.objects.get_or_create(
        conversation=conversation,
        user=target_user
    )

    # Convert to group if needed
    member_count = ConversationMember.objects.filter(
        conversation=conversation
    ).count()
    if member_count > 2 and not conversation.is_group:
        conversation.is_group = True
        if not conversation.name:
            conversation.name = f"Group #{conversation.id}"
        if conversation.created_by_id is None:
            conversation.created_by = request.user
        conversation.save(update_fields=["is_group", "name", "created_by"])

    # System message
    Message.objects.create(
        conversation=conversation,
        sender=request.user,
        recipient=None,
        content=f"{target_user.username} joined the conversation"
    )

    return JsonResponse({"status": "added"})


@login_required
@require_POST
def remove_member(request, conversation_id, user_id):
    """
    Remove a member from a group conversation.
    Creator can remove anyone. Admins can remove non-admins only.
    """
    conv = get_object_or_404(Conversation, id=conversation_id)

    if not conv.is_group:
        return JsonResponse({
            "error": "Cannot remove members from a DM"
        }, status=400)

    # Check membership
    if not ConversationMember.objects.filter(
        conversation=conv,
        user=request.user
    ).exists():
        return JsonResponse({"error": "Not a member"}, status=403)

    target_id = int(user_id)

    # Cannot remove creator
    if conv.created_by_id == target_id:
        return JsonResponse({
            "error": "Cannot remove the group creator"
        }, status=400)

    # Check if target exists
    if not ConversationMember.objects.filter(
        conversation=conv,
        user_id=target_id
    ).exists():
        return JsonResponse({"error": "User not in group"}, status=404)

    is_creator = (conv.created_by_id == request.user.id)
    is_admin = _is_group_admin(request.user, conv)

    if not (is_admin or request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"error": "No permission"}, status=403)

    # Non-creators can only remove non-admins
    if not is_creator and not (request.user.is_staff or request.user.is_superuser):
        admin_ids = _get_group_admin_ids(conv)
        admin_ids.add(conv.created_by_id)

        if target_id in admin_ids:
            return JsonResponse({
                "error": "Only the group creator can remove another admin."
            }, status=403)

    # Remove member
    ConversationMember.objects.filter(
        conversation=conv,
        user_id=target_id
    ).delete()

    # Clean up legacy admin group
    try:
        gname = _group_admin_group_name(conv.id)
        grp = Group.objects.filter(name=gname).first()
        if grp:
            grp.user_set.remove(User.objects.get(id=target_id))
    except Exception:
        pass

    return JsonResponse({"ok": True})


@login_required
@require_POST
def leave_conversation(request, conversation_id):
    """Leave a conversation. Transfers ownership if creator leaves."""
    conv = get_object_or_404(Conversation, id=conversation_id)

    # Check membership
    if not ConversationMember.objects.filter(
        conversation=conv,
        user=request.user
    ).exists():
        return JsonResponse({"error": "Not a member"}, status=403)

    # Remove membership
    ConversationMember.objects.filter(
        conversation=conv,
        user=request.user
    ).delete()

    # Transfer ownership if creator left
    if conv.is_group and conv.created_by_id == request.user.id:
        new_owner_id = (
            ConversationMember.objects.filter(conversation=conv)
            .order_by("joined_at")
            .values_list("user_id", flat=True)
            .first()
        )
        conv.created_by_id = new_owner_id
        conv.save(update_fields=["created_by"])

    return JsonResponse({"ok": True})


@login_required
@require_POST
def make_group_admin(request, conversation_id, user_id):
    """Promote a member to group admin (creator only)."""
    conv = get_object_or_404(Conversation, id=conversation_id)

    if not conv.is_group:
        return JsonResponse({"error": "Not a group"}, status=400)

    if conv.created_by_id != request.user.id:
        return JsonResponse({
            "error": "Only the group creator can change admin roles."
        }, status=403)

    # Check if member exists
    member = ConversationMember.objects.filter(
        conversation=conv,
        user_id=user_id
    ).first()
    if not member:
        return JsonResponse({"error": "User not in group"}, status=404)

    # Creator is always admin
    if int(user_id) == conv.created_by_id:
        return JsonResponse({"ok": True})

    # Set admin flag
    if not member.is_admin:
        member.is_admin = True
        member.save(update_fields=["is_admin"])

    # Sync legacy group
    try:
        gname = _group_admin_group_name(conv.id)
        grp, _ = Group.objects.get_or_create(name=gname)
        grp.user_set.add(User.objects.get(id=user_id))
    except Exception:
        pass

    return JsonResponse({"ok": True})


@login_required
@require_POST
def remove_group_admin(request, conversation_id, user_id):
    """Demote an admin to regular member (creator only)."""
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        is_group=True
    )

    # Only creator can change roles
    if conversation.created_by_id != request.user.id:
        return JsonResponse({
            "success": False,
            "error": "Only the group creator can change admin roles."
        }, status=403)

    # Creator cannot be demoted
    if int(user_id) == conversation.created_by_id:
        return JsonResponse({
            "success": False,
            "error": "The group creator cannot be removed as admin."
        }, status=400)

    member = ConversationMember.objects.filter(
        conversation=conversation,
        user_id=user_id
    ).first()
    if not member:
        return JsonResponse({
            "success": False,
            "error": "User not in group"
        }, status=404)

    # Remove admin flag
    if member.is_admin:
        member.is_admin = False
        member.save(update_fields=["is_admin"])

    # Sync legacy group
    try:
        gname = _group_admin_group_name(conversation.id)
        grp = Group.objects.filter(name=gname).first()
        if grp:
            grp.user_set.remove(User.objects.get(id=user_id))
    except Exception:
        pass

    return JsonResponse({"success": True})


@login_required
@require_POST
def transfer_group_owner(request, conversation_id, user_id):
    """Transfer group ownership to another member (creator only)."""
    conv = get_object_or_404(Conversation, id=conversation_id)

    if not conv.is_group:
        return JsonResponse({"error": "Not a group"}, status=400)

    if conv.created_by_id != request.user.id:
        return JsonResponse({"error": "No permission"}, status=403)

    if not ConversationMember.objects.filter(
        conversation=conv,
        user_id=user_id
    ).exists():
        return JsonResponse({"error": "User not in group"}, status=404)

    # Old owner becomes admin
    gname = _group_admin_group_name(conv.id)
    grp, _ = Group.objects.get_or_create(name=gname)
    grp.user_set.add(request.user)

    # Transfer ownership
    conv.created_by_id = int(user_id)
    conv.save(update_fields=["created_by"])

    return JsonResponse({"ok": True})


@login_required
@require_POST
def update_group_name(request, conversation_id):
    """Update group name (creator only)."""
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        is_group=True
    )

    if conversation.created_by_id != request.user.id:
        return JsonResponse({
            "success": False,
            "error": "Only the group creator can change the group name."
        }, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    name = (payload.get("name") or "").strip()
    if not name:
        return JsonResponse({
            "success": False,
            "error": "Group name cannot be empty."
        }, status=400)

    conversation.name = name[:128]
    conversation.save(update_fields=["name"])
    return JsonResponse({"success": True, "name": conversation.name})


@csrf_exempt
@login_required
@require_POST
def update_group_avatar(request, conversation_id):
    """Update group avatar (any member can upload)."""
    conv = get_object_or_404(Conversation, id=conversation_id)

    if not conv.is_group:
        return JsonResponse({"error": "Not a group"}, status=400)

    # Check membership
    if not ConversationMember.objects.filter(
        conversation=conv,
        user=request.user
    ).exists():
        return JsonResponse({"error": "No permission"}, status=403)

    avatar = request.FILES.get("group_avatar")
    if not avatar:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    conv.group_avatar = avatar
    conv.save(update_fields=["group_avatar"])

    return JsonResponse({"ok": True, "url": conv.group_avatar.url})


@login_required
@require_POST
def delete_group(request, conversation_id):
    """Permanently delete a group (creator only)."""
    conv = get_object_or_404(Conversation, id=conversation_id)

    if not conv.is_group:
        return JsonResponse({"error": "Not a group"}, status=400)

    if conv.created_by_id != request.user.id:
        return JsonResponse({"error": "No permission"}, status=403)

    conv.delete()
    return JsonResponse({"ok": True})


# ============================================================================
# API ENDPOINTS
# ============================================================================

@login_required
@require_GET
def users_search(request):
    """
    User search API for autocomplete.
    Optionally filters by conversation membership.
    """
    q = (request.GET.get("q") or "").strip()
    room_id = request.GET.get("room_id")

    if not q:
        return JsonResponse({"results": []})

    qs = User.objects.filter(username__icontains=q).exclude(id=request.user.id)

    # Filter by room membership if provided
    if room_id and str(room_id).isdigit():
        conv = get_object_or_404(Conversation, id=int(room_id))
        if not ConversationMember.objects.filter(
            conversation=conv,
            user=request.user
        ).exists():
            return JsonResponse({"results": []}, status=403)

        member_ids = ConversationMember.objects.filter(
            conversation=conv
        ).values_list("user_id", flat=True)
        qs = qs.exclude(id__in=member_ids)

    results = []
    for u in qs.order_by("username")[:10]:
        results.append({
            "id": u.id,
            "username": u.username,
            "avatar_url": (
                u.profile_picture.url if getattr(u, "profile_picture", None) else ""
            )
        })

    return JsonResponse({"results": results})


@login_required
@require_GET
def mention_user_suggestions(request):
    """API endpoint for @mention autocomplete."""
    q = (request.GET.get("q") or "").strip()
    if not q:
        return JsonResponse({"results": []})

    blocked_ids = _blocked_user_ids_for(request.user)

    qs = User.objects.filter(username__icontains=q).exclude(id=request.user.id)
    if blocked_ids:
        qs = qs.exclude(id__in=blocked_ids)

    results = [
        {"id": u.id, "username": u.username} 
        for u in qs.order_by("username")[:10]
    ]
    return JsonResponse({"results": results})


@login_required
@require_GET
def mention_group_suggestions(request, conversation_id):
    """API endpoint for @mention autocomplete in groups."""
    q = (request.GET.get("q") or "").strip()
    if not q:
        return JsonResponse({"results": []})

    conv = get_object_or_404(Conversation, id=conversation_id)

    # Check membership
    if not ConversationMember.objects.filter(
        conversation=conv,
        user=request.user
    ).exists():
        return JsonResponse({"results": []}, status=403)

    blocked_ids = _blocked_user_ids_for(request.user)

    member_ids = ConversationMember.objects.filter(
        conversation=conv
    ).values_list("user_id", flat=True)
    qs = User.objects.filter(
        id__in=member_ids,
        username__icontains=q
    ).exclude(id=request.user.id)
    if blocked_ids:
        qs = qs.exclude(id__in=blocked_ids)

    results = [
        {"id": u.id, "username": u.username} 
        for u in qs.order_by("username")[:10]
    ]
    return JsonResponse({"results": results})


@csrf_exempt
@require_POST
@login_required
def start_typing_room(request, room_id):
    """Signal that user is typing in a conversation room."""
    conversation = get_object_or_404(Conversation, id=room_id)

    # Check membership
    if not ConversationMember.objects.filter(
        conversation=conversation,
        user=request.user
    ).exists():
        return HttpResponseForbidden()

    # Set cache flag (expires in 3 seconds)
    cache.set(f"typing:{room_id}:{request.user.id}", True, 3)

    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
@login_required
def stop_typing_room(request, room_id):
    """Signal that user stopped typing in a conversation room."""
    conversation = get_object_or_404(Conversation, id=room_id)

    # Check membership
    if not ConversationMember.objects.filter(
        conversation=conversation,
        user=request.user
    ).exists():
        return HttpResponseForbidden()

    cache.delete(f"typing:{room_id}:{request.user.id}")

    return JsonResponse({"ok": True})


@login_required
def check_typing_room(request, room_id):
    """Check who is currently typing in a conversation room."""
    conversation = get_object_or_404(Conversation, id=room_id)

    # Check membership
    if not ConversationMember.objects.filter(
        conversation=conversation,
        user=request.user
    ).exists():
        return HttpResponseForbidden()

    member_ids = list(
        ConversationMember.objects
        .filter(conversation=conversation)
        .exclude(user=request.user)
        .values_list("user_id", flat=True)
    )

    typing_users = []
    for uid in member_ids:
        if cache.get(f"typing:{room_id}:{uid}"):
            u = (
                User.objects.filter(id=uid)
                .values_list("username", flat=True)
                .first()
            )
            if u:
                typing_users.append(u)

    return JsonResponse({
        "is_typing": bool(typing_users),
        "users": typing_users
    })


@csrf_exempt
@require_POST
@login_required
def start_typing(request, username):
    """Signal typing in DM (legacy DB-based)."""
    user = request.user
    other = User.objects.get(username=username)

    user.is_typing = True
    user.typing_to = other
    user.last_typing_time = timezone.now()
    user.save(update_fields=["is_typing", "typing_to", "last_typing_time"])

    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
@login_required
def stop_typing(request, username):
    """Stop typing signal in DM (legacy DB-based)."""
    user = request.user
    user.is_typing = False
    user.typing_to = None
    user.save(update_fields=["is_typing", "typing_to"])

    return JsonResponse({"ok": True})


@login_required
def check_typing(request, username):
    """Check if other user is typing in DM (legacy DB-based)."""
    other = User.objects.get(username=username)

    is_typing = (
        other.is_typing and
        other.typing_to_id == request.user.id
    )

    return JsonResponse({"is_typing": is_typing})


@csrf_exempt
@login_required
@require_POST
def update_message_settings(request):
    """Update user's message alert settings."""
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        data = {}

    u = request.user

    if "message_sound_enabled" in data:
        u.message_sound_enabled = bool(data["message_sound_enabled"])
    if "message_badge_enabled" in data:
        u.message_badge_enabled = bool(data["message_badge_enabled"])
    if "message_sound_choice" in data:
        choice = str(data["message_sound_choice"]).strip()
        if choice in {"ding", "pop", "chime"}:
            u.message_sound_choice = choice

    u.save(update_fields=[
        "message_sound_enabled",
        "message_badge_enabled",
        "message_sound_choice"
    ])

    return JsonResponse({"status": "success"})

@login_required
@require_http_methods(["GET"])
def api_user_settings(request):
    """
    Return user's message alert settings for JavaScript
    Called by: argonInitMessageAlertSettings() in main.js
    """
    return JsonResponse({
        'message_sound_enabled': request.user.message_sound_enabled,
        'message_sound_choice': request.user.message_sound_choice or 'ding',
        'badge_enabled': request.user.message_badge_enabled
    })

@login_required
@require_http_methods(["GET"])
def api_message_badge(request):
    """
    Return unread message count for badge updates
    Called by: argonUpdateMessageBadge() in main.js (every 3 seconds)
    """
    total_unread = 0
    
    # Get all conversations user is a member of
    memberships = ConversationMember.objects.filter(
        user=request.user
    ).select_related('conversation')
    
    for mem in memberships:
        conv = mem.conversation
        
        # Skip hidden conversations
        if conv.hidden_by.filter(id=request.user.id).exists():
            continue
        
        if conv.is_group:
            # Group chat: count messages after last read time
            last_read = mem.last_read_at or conv.created_at
            unread = conv.messages.exclude(sender=request.user).filter(
                timestamp__gt=last_read
            ).count()
        else:
            # DM: count unread messages from other user
            other_user = User.objects.filter(
                conversation_memberships__conversation=conv
            ).exclude(id=request.user.id).first()
            
            if other_user:
                unread = conv.messages.filter(
                    sender=other_user,
                    recipient=request.user,
                    is_read=False
                ).count()
            else:
                unread = 0
        
        total_unread += unread
    
    return JsonResponse({
        'count': total_unread,
        'badge_enabled': request.user.message_badge_enabled
    })

@csrf_exempt
@login_required
def submit_report(request):
    """Submit content report to administrators."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    data = request.POST
    target_type = data.get('target_type')
    target_id = data.get('target_id')
    reason = data.get('reason', '').strip()

    if not target_type or not target_id or not reason:
        return JsonResponse({"error": "Missing required fields"}, status=400)

    # Get target object
    try:
        if target_type == 'post':
            target = Post.objects.get(id=target_id)
        elif target_type == 'comment':
            target = Comment.objects.get(id=target_id)
        elif target_type == 'user':
            target = User.objects.get(id=target_id)
        elif target_type == 'message':
            target = Message.objects.get(id=target_id)
        else:
            return JsonResponse({"error": "Invalid target_type"}, status=400)
    except (Post.DoesNotExist, Comment.DoesNotExist, 
            User.DoesNotExist, Message.DoesNotExist):
        return JsonResponse({"error": "Target not found"}, status=404)

    # Send email to admins
    try:
        subject = f"User report: {target_type} #{target_id}"
        html_content = render_to_string("network/emails/report_notification.html", {
            'reporter': request.user,
            'target_type': target_type,
            'target_id': target_id,
            'reason': reason,
            'target': target
        })
        text_content = strip_tags(html_content)
        admin_emails = [
            a[1] for a in settings.ADMINS
        ] if hasattr(settings, 'ADMINS') and settings.ADMINS else [
            settings.DEFAULT_FROM_EMAIL
        ]
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            admin_emails
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)
    except Exception:
        logger.exception("Failed to send report email for %s %s", target_type, target_id)
        return JsonResponse({
            "error": "Could not submit report at this time"
        }, status=500)

    return JsonResponse({"status": "success", "message": "Report submitted"})


@require_GET
def search_gifs(request):
    """
    Returns GIF/STICKER results for the picker.

    UX improvements:
    - Uses /trending endpoints when query is empty or "trending" (true trending)
    - Returns lightweight URLs for grid (fast on mobile)
    - Also returns full/original URLs so frontend can store best quality on selection
    - Adds short caching to feel instant and reduce API calls
    - Keeps placeholder fallback consistent (always returns 12 items if possible)
    """
    query = (request.GET.get('q') or '').strip()
    q_norm = query.lower()
    media_type = (request.GET.get('type', 'gifs') or 'gifs').lower()
    media_type = 'stickers' if media_type == 'stickers' else 'gifs'

    api_key = os.getenv('GIPHY_API_KEY')

    # Cache for repeated searches (huge speedup)
    cache_key = f"giphy:v2:{media_type}:{q_norm or 'trending'}"
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse(cached)

    items = []
    source = 'local_placeholder'

    def pick_urls(images: dict):
        """
        Prefer small/fast for grid, but also return a good full URL for posting.
        """
        preview = (
            images.get('fixed_width_small', {}).get('url') or
            images.get('preview_gif', {}).get('url') or
            images.get('fixed_height_small', {}).get('url') or
            images.get('fixed_height', {}).get('url')
        )
        full = (
            images.get('original', {}).get('url') or
            images.get('downsized', {}).get('url') or
            images.get('fixed_height', {}).get('url') or
            preview
        )
        return preview, full

    # ---- GIPHY API ----
    if api_key:
        is_trending = (q_norm == '' or q_norm == 'trending')

        if media_type == 'stickers':
            endpoint = 'https://api.giphy.com/v1/stickers/trending' if is_trending else 'https://api.giphy.com/v1/stickers/search'
        else:
            endpoint = 'https://api.giphy.com/v1/gifs/trending' if is_trending else 'https://api.giphy.com/v1/gifs/search'

        params = {
            'api_key': api_key,
            'limit': 12,
            'rating': 'g',
            'lang': 'en',
            'bundle': 'messaging_non_clips',
        }
        if not is_trending:
            params['q'] = query

        try:
            response = requests.get(
                endpoint,
                params=params,
                timeout=8,
                headers={"User-Agent": "Argon/1.0 (GIF Picker)"}
            )
            response.raise_for_status()
            data = response.json()

            for it in data.get('data', []):
                images = it.get('images') or {}
                preview_url, full_url = pick_urls(images)
                if not preview_url:
                    continue

                items.append({
                    "id": it.get("id"),
                    "title": it.get("title") or "",
                    "preview_url": preview_url,   # use in picker grid (fast)
                    "url": full_url,              # store/send this on selection (better quality)
                    "width": (images.get('fixed_width_small', {}) or {}).get('width'),
                    "height": (images.get('fixed_width_small', {}) or {}).get('height'),
                })

            source = 'giphy'
        except Exception as e:
            logger.warning(f"Giphy API error: {e}")
            items = []
            source = 'giphy_error'

    # ---- PLACEHOLDERS ----
    if not items:
        # Simple placeholders: (preview_url == url)
        placeholder_gifs = {
            'hello': ["https://media.giphy.com/media/3o7aCTPPm4OHfRLSH6/giphy.gif"],
            'happy': ["https://media.giphy.com/media/3o7abAHdYvZdBNnGZq/giphy.gif"],
            'cat': ["https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif"],
            'trending': [
                "https://media.giphy.com/media/3o7aCTPPm4OHfRLSH6/giphy.gif",
                "https://media.giphy.com/media/l46Cy1rHbQ92uuLXa/giphy.gif",
                "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif",
            ],
        }
        placeholder_stickers = {
            'hello': ["https://media.giphy.com/media/3o7TKSha51ATTx9KzC/giphy.gif"],
            'happy': ["https://media.giphy.com/media/3o7abAHdYvZdBNnGZq/giphy.gif"],
            'trending': ["https://media.giphy.com/media/3o7TKSha51ATTx9KzC/giphy.gif"],
        }

        data_source = placeholder_stickers if media_type == 'stickers' else placeholder_gifs
        base = data_source.get(q_norm) or data_source.get('trending') or data_source.get('hello') or []

        # Fill to 12 so UI grid stays consistent
        urls = []
        if base:
            while len(urls) < 12:
                urls.extend(base)
            urls = urls[:12]

        items = [{
            "id": None,
            "title": "",
            "preview_url": u,
            "url": u
        } for u in urls]

        source = 'local_placeholder' if source != 'giphy_error' else 'giphy_error_fallback'

    payload = {
        "items": items,           
        "gifs": [x["preview_url"] for x in items], 
        "type": media_type,
        "count": len(items),
        "source": source
    }

    cache.set(cache_key, payload, 60)  
    return JsonResponse(payload)
