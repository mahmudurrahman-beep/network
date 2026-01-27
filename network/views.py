import os
import json
import logging  
import pytz
import requests

from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives, send_mail
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.html import strip_tags
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string 
from django.views.decorators.http import require_GET
from django.core.cache import cache
from .models import User, Post, PostMedia, Follow, Notification, Message, Comment, Block, PrivacySettings


# Logger
logger = logging.getLogger(__name__)


def index(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('all_posts'))
    return render(request, "network/landing.html")


def login_view(request):
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
    logout(request)
    return HttpResponseRedirect(reverse("index"))



def activate(request, token):
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


@login_required
def new_post(request):
    if request.method == "POST":
        content = request.POST.get('content', '').strip()
        if not content:
            return JsonResponse({"error": "Content required"}, status=400)
        post = Post.objects.create(user=request.user, content=content)
        for f in request.FILES.getlist('media_files'):
            if f.content_type.startswith('audio/'):
                return JsonResponse({"error": "Audio files not supported"}, status=400)
            media_type = 'video' if f.content_type.startswith('video') else 'image'
            PostMedia.objects.create(post=post, file=f, media_type=media_type)
        return JsonResponse({"message": "Posted!", "post_id": post.id}, status=201)
    return render(request, "network/new_post.html")


@csrf_exempt
@login_required
def toggle_follow(request, username):
    target_user = get_object_or_404(User, username=username)

    if request.user == target_user:
        return JsonResponse({"error": "Cannot follow yourself"}, status=400)
    
    # CHECK: If blocked in either direction, prevent follow
    is_blocked = Block.objects.filter(blocker=request.user, blocked=target_user).exists()
    has_blocked_me = Block.objects.filter(blocker=target_user, blocked=request.user).exists()
    
    if is_blocked:
        return JsonResponse({"error": "You have blocked this user. Unblock them first to follow."}, status=403)
    
    if has_blocked_me:
        return JsonResponse({"error": "This user has blocked you. You cannot follow them."}, status=403)
    
    # Continue with existing follow logic
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
    target_user = get_object_or_404(User, username=username)
    if request.user == target_user:
        return JsonResponse({"error": "Cannot block yourself"}, status=400)
    block, created = Block.objects.get_or_create(blocker=request.user, blocked=target_user)
    if not created:
        block.delete()
        action = "unblocked"
    else:
        action = "blocked"
    return JsonResponse({"action": action})


@login_required
def unblock_user(request, username):
    target_user = get_object_or_404(User, username=username)
    Block.objects.filter(blocker=request.user, blocked=target_user).delete()
    messages.success(request, f"You have unblocked {username}.")
    return redirect('privacy_settings')


# Backwards-compatible alias
unblock_usr = unblock_user


@login_required
def privacy_settings(request):
    # Ensure privacy settings exist
    privacy_settings_obj, _ = PrivacySettings.objects.get_or_create(
        user=request.user,
        defaults={'post_visibility': 'universal'}
    )

    if request.method == "POST":
        privacy_settings_obj.post_visibility = request.POST.get('post_visibility', 'universal')
        privacy_settings_obj.save()
        messages.success(request, "Privacy settings updated.")
        return redirect('privacy_settings')

    # Prefer related_name if available, otherwise query Block directly
    try:
        # If your Block model defines related_name='blocks' on blocker FK:
        blocked_qs = request.user.blocks.all().order_by('-timestamp')
    except Exception:
        # Fallback explicit query (adjust field names if different)
        blocked_qs = Block.objects.filter(blocker=request.user).order_by('-timestamp')

    return render(request, "network/privacy_settings.html", {
        'blocked_users': blocked_qs,
        'privacy_settings': privacy_settings_obj,
        'user': request.user,   # ensures template { user.username } works
    })


@csrf_exempt
@login_required
def submit_report(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    data = request.POST
    target_type = data.get('target_type')
    target_id = data.get('target_id')
    reason = data.get('reason', '').strip()

    if not target_type or not target_id or not reason:
        return JsonResponse({"error": "Missing required fields"}, status=400)

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
    except (Post.DoesNotExist, Comment.DoesNotExist, User.DoesNotExist, Message.DoesNotExist):
        return JsonResponse({"error": "Target not found"}, status=404)

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
        admin_emails = [a[1] for a in settings.ADMINS] if hasattr(settings, 'ADMINS') and settings.ADMINS else [settings.DEFAULT_FROM_EMAIL]
        msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, admin_emails)
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)
    except Exception:
        return JsonResponse({"error": "Could not submit report at this time"}, status=500)

    return JsonResponse({"status": "success", "message": "Report submitted"})


@csrf_exempt
@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, user=request.user)
    if request.method == "PUT":
        data = json.loads(request.body)
        post.content = data.get('content', post.content)
        post.save()
        return JsonResponse({"message": "Post updated"})
    return JsonResponse({"error": "PUT request required"}, status=400)

@csrf_exempt
@login_required
def toggle_vote(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    data = json.loads(request.body)
    value = data['value']  # 1 for up, -1 for down
    
    if value == 1:
        field = post.thumbs_up
        opposite = post.thumbs_down
    else:
        field = post.thumbs_down
        opposite = post.thumbs_up
    
    # Toggle vote
    if request.user in field.all():
        field.remove(request.user)  # Undo vote
    else:
        opposite.remove(request.user)  # Remove opposite vote if present
        field.add(request.user)
        # Notification
        if request.user != post.user:
            Notification.objects.create(
                user=post.user,
                actor=request.user,
                verb="voted on your post",
                post=post
            )
    
    # Refresh the post object to get updated counts
    post.refresh_from_db()
    
    # Return ALL the data JavaScript expects (matching post_detail view)
    return JsonResponse({
        "up": post.thumbs_up.count(),
        "down": post.thumbs_down.count(),
        "user_up": request.user in post.thumbs_up.all(),  # ADD THIS
        "user_down": request.user in post.thumbs_down.all()  # ADD THIS
    }) 

@login_required
def notifications_view(request):
    notifs = request.user.notifications.all()[:30]
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return render(request, "network/notifications.html", {'notifications': notifs})


@csrf_exempt
@login_required
def mark_notifications_read(request):
    if request.method == "POST":
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({"status": "success"})
    return JsonResponse({"error": "POST required"}, status=400)


# NEW: Notification clearing views
@login_required
@require_POST
def clear_all_notifications(request):
    """Delete all notifications for current user"""
    request.user.notifications.all().delete()
    return JsonResponse({'success': True, 'message': 'All notifications cleared.'})

@login_required  
@require_POST
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    request.user.notifications.mark_all_as_read()
    return JsonResponse({'success': True, 'message': 'All notifications marked as read.'})

@login_required
@require_POST
def delete_notification(request, notification_id):
    """Delete a specific notification"""
    try:
        notification = request.user.notifications.get(id=notification_id)
        notification.delete()
        return JsonResponse({'success': True, 'message': 'Notification deleted.'})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification not found.'}, status=404)
# END NEW


@login_required
def edit_profile(request):
    if request.method == "POST":
        user = request.user
        new_username = request.POST.get('username', '').strip()
        if new_username and new_username != user.username:
            if User.objects.filter(username__iexact=new_username).exists():
                timezone_choices = [(tz, tz) for tz in pytz.all_timezones]
                return render(request, "network/edit_profile.html", {
                    "message": "Username already taken.",
                    "timezone_choices": timezone_choices,
                })
            user.username = new_username
        user.bio = request.POST.get('bio', '')
        user.timezone = request.POST.get('timezone', 'UTC')
        user.gender = request.POST.get('gender', '')
        user.save()
        return redirect('profile', username=user.username)
    timezone_choices = [(tz, tz) for tz in pytz.all_timezones]
    return render(request, "network/edit_profile.html", {
        'timezone_choices': timezone_choices
    })


@login_required
def messages_inbox(request):
    conversations = []
    sent = request.user.sent_messages.values('recipient').distinct()
    received = request.user.received_messages.values('sender').distinct()
    users = set()
    for s in sent:
        users.add(s['recipient'])
    for r in received:
        users.add(r['sender'])

    for u in users:
        other_user = User.objects.get(id=u)
        if request.user.hidden_conversations.filter(id=other_user.id).exists():
            continue

        latest = Message.objects.filter(
            (Q(sender=request.user) & Q(recipient=other_user)) |
            (Q(sender=other_user) & Q(recipient=request.user))
        ).order_by('-timestamp').first()
        unread = Message.objects.filter(sender=other_user, recipient=request.user, is_read=False).count()
        conversations.append({
            'user': other_user,
            'latest_message': latest,
            'unread_count': unread
        })

    return render(request, "network/messages/messages_inbox.html", {'conversations': conversations})


@login_required
def conversation(request, username):
    other_user = get_object_or_404(User, username=username)
    
    # CHECK FOR BLOCKS BEFORE ALLOWING MESSAGING
    is_blocked = False
    has_blocked_me = False
    try:
        is_blocked = Block.objects.filter(blocker=request.user, blocked=other_user).exists()
        has_blocked_me = Block.objects.filter(blocker=other_user, blocked=request.user).exists()
    except (Block.DoesNotExist, AttributeError):
        pass
    
    if is_blocked or has_blocked_me:
        messages.error(request, "Cannot message this user due to block settings.")
        return redirect('messages_inbox')
    
    if request.user == other_user:
        return HttpResponseRedirect(reverse('messages_inbox'))

    msgs = Message.objects.filter(
        Q(sender=request.user, recipient=other_user) |
        Q(sender=other_user, recipient=request.user)
    ).order_by('timestamp')

    Message.objects.filter(sender=other_user, recipient=request.user, is_read=False).update(is_read=True)

    if request.method == "POST":
        content = request.POST.get('content', '').strip()
        media_file = request.FILES.get('media')

        if content or media_file:
            msg = Message.objects.create(
                sender=request.user,
                recipient=other_user,
                content=content or ''
            )

            if media_file:
                content_type = media_file.content_type
                if content_type == 'image/gif':
                    media_type = 'gif'
                elif content_type.startswith('image/'):
                    media_type = 'image'
                elif content_type.startswith('video/'):
                    media_type = 'video'
                else:
                    ext = os.path.splitext(media_file.name)[1].lower()
                    if ext == '.gif':
                        media_type = 'gif'
                    elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                        media_type = 'image'
                    elif ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                        media_type = 'video'
                    else:
                        media_type = 'image'
                msg.media = media_file
                msg.media_type = media_type
                msg.save()

            request.user.hidden_conversations.remove(other_user)
            other_user.hidden_conversations.remove(request.user)

        return HttpResponseRedirect(reverse('conversation', args=[username]))

    return render(request, "network/messages/conversation.html", {
        'other_user': other_user,
        'messages': msgs
    }) 


@csrf_exempt
@login_required
def quick_upload_picture(request):
    if request.method == "POST" and 'profile_picture' in request.FILES:
        request.user.profile_picture = request.FILES['profile_picture']
        request.user.save()
    return HttpResponseRedirect(reverse('profile', args=[request.user.username]))


@csrf_exempt
@login_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, user=request.user)
    if request.method == "POST":
        post.delete()
        return JsonResponse({"message": "Post deleted"})
    return JsonResponse({"error": "POST required"}, status=400)


@csrf_exempt
@login_required
def delete_comment(request, comment_id):
    if request.method == "POST":
        try:
            comment = Comment.objects.get(id=comment_id, user=request.user)
            comment.delete()
            return JsonResponse({"status": "success", "message": "Comment deleted"})
        except Comment.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Not found or not yours"}, status=403)
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


@csrf_exempt
@login_required
def delete_message(request, message_id):
    if request.method == "POST":
        try:
            message = Message.objects.get(id=message_id, sender=request.user)
            message.delete()
            return JsonResponse({"message": "Message deleted"})
        except Message.DoesNotExist:
            return JsonResponse({"error": "Message not found or not yours"}, status=404)
    return JsonResponse({"error": "POST required"}, status=400)


@csrf_exempt
@login_required
def edit_comment(request, comment_id):
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


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    if request.method == "POST":
        content = request.POST.get('content', '').strip()
        parent_id = request.POST.get('parent_id')
        media_url = request.POST.get('media_url', '')
        media_type = request.POST.get('media_type', 'text')

        if not content and not media_url:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"error": "Comment cannot be empty"}, status=400)
            messages.error(request, "Comment cannot be empty.")
            return redirect('all_posts')

        parent = None
        if parent_id:
            try:
                parent = Comment.objects.get(id=parent_id, post=post)

                # ✅ MAX DEPTH = 1
                # parent is allowed only if it's a root comment (parent.parent must be None)
                # i.e. you can reply to root, but cannot reply to a reply
                depth = 0
                current = parent
                while current.parent:
                    depth += 1
                    current = current.parent

                if depth >= 1:
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({"error": "Maximum reply depth reached"}, status=400)
                    messages.error(request, "Maximum reply depth reached.")
                    return redirect('all_posts')

            except Comment.DoesNotExist:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({"error": "Invalid parent comment"}, status=400)
                messages.error(request, "Invalid parent comment.")
                return redirect('all_posts')

        comment = Comment.objects.create(
            post=post,
            user=request.user,
            content=content,
            parent=parent,
            media_url=media_url,
            media_type=media_type
        )

        if post.user != request.user:
            Notification.objects.create(
                user=post.user,
                actor=request.user,
                verb="commented on your post",
                post=post
            )

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                "status": "success",
                "comment_id": comment.id,
                "user": comment.user.username,
                "avatar": comment.user.profile_picture.url if comment.user.profile_picture else '/static/default-avatar.png',
                "content": comment.content,
                "media_url": comment.media_url,
                "media_type": comment.media_type,
                "timestamp": comment.timestamp.strftime("%b %d, %Y • %I:%M %p"),
                "parent_id": parent_id or None
            })

        messages.success(request, "Comment added!")
        return redirect('all_posts')

    return redirect('all_posts')


@csrf_exempt
@login_required
def delete_conversation(request, username):
    other_user = get_object_or_404(User, username=username)
    if request.method == "POST":
        request.user.hidden_conversations.add(other_user)
        return JsonResponse({"message": "Conversation hidden"})
    return JsonResponse({"error": "POST required"}, status=400)

@login_required
def all_posts(request):
    base_qs = Post.objects.select_related('user').prefetch_related(
        'media', 'thumbs_up', 'thumbs_down', 'comments__user'
    ).order_by('-timestamp')

    visible_posts = []
    for post in base_qs:
        try:
            if Block.objects.filter(blocker=request.user, blocked=post.user).exists():
                continue
        except (Block.DoesNotExist, AttributeError):
            pass

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
            post.user.followers.filter(follower=request.user).exists() or
            post.user.following.filter(followed=request.user).exists()
        ):
            visible_posts.append(post)

    post_ids = [p.id for p in visible_posts]
    posts = Post.objects.filter(id__in=post_ids).order_by('-timestamp').prefetch_related(
        'media', 'thumbs_up', 'thumbs_down', 'comments__user'
    )

    for post in posts:
        post.root_comments = post.comments.filter(parent__isnull=True).order_by('timestamp')

    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "network/all_posts.html", {'page_obj': page_obj})

@login_required
def post_detail(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related('user').prefetch_related(
            'media', 'thumbs_up', 'thumbs_down', 'comments__user', 'comments__parent'
        ),
        id=post_id
    )

    try:
        if Block.objects.filter(blocker=request.user, blocked=post.user).exists():
            messages.error(request, "You cannot view this post.")
            return redirect('all_posts')
    except (Block.DoesNotExist, AttributeError):
        pass

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
        'is_downvoted': request.user in post.thumbs_down.all(),
    }
    return render(request, "network/post_detail.html", context)

@login_required
def profile(request, username):
    profile_user = get_object_or_404(User, username=username)

    is_blocked = False
    has_blocked_me = False
    try:
        is_blocked = Block.objects.filter(blocker=request.user, blocked=profile_user).exists()
        has_blocked_me = Block.objects.filter(blocker=profile_user, blocked=request.user).exists()
    except (Block.DoesNotExist, AttributeError):
        pass
    
    # FIXED: Add self-check to prevent following/messaging yourself
    can_follow = not (is_blocked or has_blocked_me) and request.user != profile_user
    can_message = not (is_blocked or has_blocked_me) and request.user != profile_user
    
    posts_qs = profile_user.posts.select_related('user').prefetch_related('media', 'thumbs_up', 'thumbs_down', 'comments__user').order_by('-timestamp')

    for post in posts_qs:
        post.root_comments = post.comments.filter(parent__isnull=True).order_by('timestamp')

    paginator = Paginator(posts_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    is_following = False
    if request.user != profile_user:
        is_following = Follow.objects.filter(follower=request.user, followed=profile_user).exists()

    privacy_settings, _ = PrivacySettings.objects.get_or_create(user=profile_user, defaults={'post_visibility': 'universal'})

    return render(request, "network/profile.html", {
        'profile_user': profile_user,
        'page_obj': page_obj,
        'is_following': is_following,
        'is_blocked': is_blocked,
        'has_blocked_me': has_blocked_me,
        'can_follow': can_follow,          # FIXED: Now correct
        'can_message': can_message,        # FIXED: Now correct
        'privacy_settings': privacy_settings,
        'followers_count': profile_user.followers.count(),
        'following_count': profile_user.following.count(),
    }) 

@login_required
def discover_users(request):
    query = request.GET.get('q', '').strip()
    users = User.objects.exclude(id=request.user.id)

    if query:
        users = users.filter(username__icontains=query)

    # Get block status for template context
    blocked_user_ids = set(Block.objects.filter(blocker=request.user).values_list('blocked_id', flat=True))
    blocked_by_user_ids = set(Block.objects.filter(blocked=request.user).values_list('blocker_id', flat=True))
    
    return render(request, "network/discover_users.html", {
        'users': users,
        'query': query,
        'blocked_user_ids': blocked_user_ids,
        'blocked_by_user_ids': blocked_by_user_ids,
    }) 

@login_required
def followers_list(request, username):
    profile_user = get_object_or_404(User, username=username)
    followers = User.objects.filter(following__followed=profile_user)

    try:
        blocked_user_ids = Block.objects.filter(blocker=request.user).values_list('blocked_id', flat=True)
        followers = followers.exclude(id__in=blocked_user_ids)
    except (Block.DoesNotExist, AttributeError):
        pass

    is_following_dict = {str(f.id): request.user.following.filter(followed=f).exists() for f in followers}

    return render(request, "network/followers_list.html", {
        'profile_user': profile_user,
        'users': followers,
        'list_type': 'Followers',
        'is_following_dict': is_following_dict
    })


@login_required
def following_list(request, username):
    profile_user = get_object_or_404(User, username=username)
    following = User.objects.filter(followers__follower=profile_user)

    try:
        blocked_user_ids = Block.objects.filter(blocker=request.user).values_list('blocked_id', flat=True)
        following = following.exclude(id__in=blocked_user_ids)
    except (Block.DoesNotExist, AttributeError):
        pass

    is_following_dict = {str(u.id): request.user.following.filter(followed=u).exists() for u in following}

    return render(request, "network/followers_list.html", {
        'profile_user': profile_user,
        'users': following,
        'list_type': 'Following',
        'is_following_dict': is_following_dict
    })


@login_required
def following(request):
    followed_user_ids = request.user.following.values_list('followed_id', flat=True)
    filtered_posts = []

    for post in Post.objects.filter(user__id__in=followed_user_ids).select_related('user').prefetch_related('media', 'comments__user'):
        try:
            if Block.objects.filter(blocker=request.user, blocked=post.user).exists():
                continue
        except (Block.DoesNotExist, AttributeError):
            pass

        privacy_settings, _ = PrivacySettings.objects.get_or_create(user=post.user, defaults={'post_visibility': 'universal'})
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
    posts = Post.objects.filter(id__in=post_ids).order_by('-timestamp').prefetch_related('media', 'thumbs_up', 'thumbs_down', 'comments__user')

    for post in posts:
        post.root_comments = post.comments.filter(parent__isnull=True).order_by('timestamp')

    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "network/following.html", {'page_obj': page_obj})

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
        "items": items,           # <-- NEW: richer objects
        "gifs": [x["preview_url"] for x in items],  # <-- compatibility: your JS already expects "gifs"
        "type": media_type,
        "count": len(items),
        "source": source
    }

    cache.set(cache_key, payload, 60)  # 60s cache
    return JsonResponse(payload)



# NEW API View for Interaction Check
@login_required
def check_interaction(request, username):
    target_user = get_object_or_404(User, username=username)
    
    is_blocked = Block.objects.filter(blocker=request.user, blocked=target_user).exists()
    has_blocked_me = Block.objects.filter(blocker=target_user, blocked=request.user).exists()
    
    can_interact = not (is_blocked or has_blocked_me)
    
    return JsonResponse({
        'can_interact': can_interact,
        'message': 'Cannot interact with this user due to block settings.' if not can_interact else ''
    })      
    
    
