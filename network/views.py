import os
import json
import logging
import pytz
import requests

from datetime import datetime

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

from .models import User, Post, PostMedia, Follow, Notification, Message, Comment, Block, PrivacySettings




def index(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('all_posts'))
    else:
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
                else:
                    messages.error(request, "Account is inactive. Please check your email to activate.")
            else:
                messages.error(request, "Invalid password.")
        else:
            messages.error(request, "No account found with that username or email.")
    
    return render(request, "network/login.html")

def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))

# Set up logger (logs to Koyeb console)
logger = logging.getLogger(__name__)

def register(request):
    if request.method == "POST":
        # Safely get and clean form data
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirmation = request.POST.get("confirmation", "")

        # Validation
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

        # Return early if validation errors
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, "network/register.html")

        try:
            # Check duplicates before creation
            if User.objects.filter(username=username).exists():
                messages.error(request, "Username already taken.")
                return render(request, "network/register.html")

            if User.objects.filter(email=email).exists():
                messages.error(request, "Email already registered.")
                return render(request, "network/register.html")

            # Create inactive user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            user.is_active = False

            # Generate and save activation token (using your existing field)
            user.activation_token = get_random_string(32)
            user.save()

            # Build activation link
            try:
                activation_link = request.build_absolute_uri(
                    reverse('activate', kwargs={'token': user.activation_token})
                )
            except Exception:
                activation_link = f"{request.scheme}://{request.get_host()}/activate/{user.activation_token}/"

            # Email context
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

            # Render HTML email
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

            # Send email
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
                # Cleanup user if email fails
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

    # GET request - empty form
    return render(request, "network/register.html")

def activate(request, token):
    try:
        user = User.objects.get(activation_token=token, is_active=False)
        user.is_active = True
        user.activation_token = '' # Clear token after use
        user.save()
        login(request, user)
        messages.success(request, "Account activated successfully! Welcome to Argon Network.")
        return redirect('index') # or 'all_posts' or 'profile'
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
                return JsonResponse({"error": "Audio files not supported"}, status=400)  # Or add 'audio' type to PostMedia
            media_type = 'video' if f.content_type.startswith('video') else 'image'
            PostMedia.objects.create(post=post, file=f, media_type=media_type)
        return JsonResponse({"message": "Posted!", "post_id": post.id}, status=201)
    return render(request, "network/new_post.html")

@login_required
def all_posts(request):
    posts = Post.objects.all().order_by('-timestamp').prefetch_related('media', 'thumbs_up', 'thumbs_down', 'comments__user')
    # Add root_comments for nested display (from local)
    for post in posts:
        post.root_comments = post.comments.filter(parent__isnull=True).order_by('timestamp')
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, "network/all_posts.html", {'page_obj': page_obj})

@login_required
def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    posts = profile_user.posts.all().order_by('-timestamp').prefetch_related('media', 'thumbs_up', 'thumbs_down', 'comments__user')
    # Add root_comments (from local)
    for post in posts:
        post.root_comments = post.comments.filter(parent__isnull=True).order_by('timestamp')
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
   
    is_following = Follow.objects.filter(follower=request.user, followed=profile_user).exists() if request.user != profile_user else False
   
    return render(request, "network/profile.html", {
        'profile_user': profile_user,
        'page_obj': page_obj,
        'is_following': is_following,
        'followers_count': profile_user.followers.count(),
        'following_count': profile_user.following.count(),
    })


@csrf_exempt
@login_required
def toggle_follow(request, username):
    target_user = get_object_or_404(User, username=username)
   
    if request.user == target_user:
        return JsonResponse({"error": "Cannot follow yourself"}, status=400)
   
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
   
    # Return both counts
    return JsonResponse({
        "action": action,
        "followers": target_user.followers.count(),
        "following": target_user.following.count()
    })

@csrf_exempt
@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, user=request.user) # only own posts
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
    value = data['value'] # 1 for up, -1 for down
   
    if value == 1:
        field = post.thumbs_up
        opposite = post.thumbs_down
    else:
        field = post.thumbs_down
        opposite = post.thumbs_up
   
    if request.user in field.all():
        field.remove(request.user) # Undo vote
    else:
        opposite.remove(request.user) # Remove opposite vote if present
        field.add(request.user)
        # Notification
        if request.user != post.user:
            Notification.objects.create(
                user=post.user,
                actor=request.user,
                verb="voted on your post",
                post=post
            )
   
    return JsonResponse({
        "up": post.thumbs_up.count(),
        "down": post.thumbs_down.count()
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
    # Get unique conversations (latest message per recipient/sender)
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
        # Skip if hidden
        if request.user.hidden_conversations.filter(id=other_user.id).exists():
            continue
       
        latest = Message.objects.filter(
            (Q(sender=request.user) & Q(recipient=other_user)) |
            (Q(sender=other_user) & Q(recipient=request.user))
        ).first()
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
    if request.user == other_user:
        return HttpResponseRedirect(reverse('messages_inbox'))
   
    messages = Message.objects.filter(
        Q(sender=request.user, recipient=other_user) |
        Q(sender=other_user, recipient=request.user)
    ).order_by('timestamp')
   
    # Mark messages as read
    Message.objects.filter(sender=other_user, recipient=request.user, is_read=False).update(is_read=True)
   
    if request.method == "POST":
        content = request.POST.get('content', '').strip()
        media_file = request.FILES.get('media')
       
        if content or media_file:
            # Create message
            msg = Message.objects.create(
                sender=request.user,
                recipient=other_user,
                content=content or ''
            )
           
            # Handle media upload
            if media_file:
                # Determine media type
                content_type = media_file.content_type
                if content_type == 'image/gif':
                    media_type = 'gif'
                elif content_type.startswith('image/'):
                    media_type = 'image'
                elif content_type.startswith('video/'):
                    media_type = 'video'
                else:
                    # Check extension as fallback
                    ext = os.path.splitext(media_file.name)[1].lower()
                    if ext == '.gif':
                        media_type = 'gif'
                    elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                        media_type = 'image'
                    elif ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                        media_type = 'video'
                    else:
                        media_type = 'image' # default
               
                # Save media to message
                msg.media = media_file
                msg.media_type = media_type
                msg.save()
           
            # Unhide for YOU (sender) so you see your own message
            request.user.hidden_conversations.remove(other_user)
           
            # Unhide for recipient (so conversation reappears)
            other_user.hidden_conversations.remove(request.user)
       
        return HttpResponseRedirect(reverse('conversation', args=[username]))
   
    return render(request, "network/messages/conversation.html", {
        'other_user': other_user,
        'messages': messages
    })

@csrf_exempt
@login_required
def quick_upload_picture(request):
    if request.method == "POST" and 'profile_picture' in request.FILES:
        request.user.profile_picture = request.FILES['profile_picture']
        request.user.save()
    return HttpResponseRedirect(reverse('profile', args=[request.user.username]))

@login_required
def discover_users(request):
    query = request.GET.get('q', '')
    users = User.objects.exclude(id=request.user.id)
    if query:
        users = users.filter(username__icontains=query)
    return render(request, "network/discover_users.html", {'users': users, 'query': query})

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
            comment = Comment.objects.get(id=comment_id, user=request.user)  # No 404 – handle manually
            comment.delete()
            return JsonResponse({"message": "Comment deleted"})
        except Comment.DoesNotExist:
            return JsonResponse({"error": "Comment not found or not yours"}, status=404)
    return JsonResponse({"error": "POST required"}, status=400)

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
                # Depth limit (max 4 levels)
                depth = 0
                current = parent
                while current.parent:
                    depth += 1
                    current = current.parent
                if depth >= 4:
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
        # Hide the conversation for you (add to hidden_conversations)
        request.user.hidden_conversations.add(other_user)
        return JsonResponse({"message": "Conversation hidden"})
    return JsonResponse({"error": "POST required"}, status=400)

@login_required
def followers_list(request, username):
    profile_user = get_object_or_404(User, username=username)
    followers = User.objects.filter(following__followed=profile_user)
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
    is_following_dict = {str(f.id): request.user.following.filter(followed=f).exists() for f in following}
    return render(request, "network/followers_list.html", {
        'profile_user': profile_user,
        'users': following,
        'list_type': 'Following',
        'is_following_dict': is_following_dict
    })  
    
    
@login_required
def following(request):
    followed_users = request.user.following.values_list('followed_id', flat=True)
    posts = Post.objects.filter(user__id__in=followed_users).order_by('-timestamp').prefetch_related('media', 'thumbs_up', 'thumbs_down', 'comments__user')
    for post in posts:
        post.root_comments = post.comments.filter(parent__isnull=True).order_by('timestamp')
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, "network/following.html", {'page_obj': page_obj})

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
            message = Message.objects.get(id=message_id, sender=request.user)  # Only own messages
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

@csrf_exempt
def search_gifs(request):
    query = request.GET.get('q', 'trending').strip().lower()
    media_type = request.GET.get('type', 'gifs').lower()  # 'gifs' or 'stickers'
    
    api_key = os.getenv('GIPHY_API_KEY')
    
    if api_key:
        # Production: Real Giphy API
        if media_type == 'stickers':
            endpoint = 'https://api.giphy.com/v1/stickers/search'
        else:
            endpoint = 'https://api.giphy.com/v1/gifs/search'
            
        params = {
            'api_key': api_key,
            'q': query or 'trending',
            'limit': 12,           # Good balance: enough for grid, not too many
            'rating': 'g',         # Family-friendly
            'lang': 'en',
            'bundle': 'messaging_non_clips'
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=8)
            response.raise_for_status()
            data = response.json()
            gifs = [item['images']['fixed_height']['url'] for item in data.get('data', [])]
            source = 'giphy'
        except Exception as e:
            print(f"Giphy API error: {e}")
            gifs = []  # Fallback empty on error
            source = 'giphy_error'
    else:
        # Local dev fallback (your placeholders)
        placeholder_gifs = {
            'hello': ["https://media.giphy.com/media/3o7aCTPPm4OHfRLSH6/giphy.gif"],
            'happy': ["https://media.giphy.com/media/3o7abAHdYvZdBNnGZq/giphy.gif"],
            'cat': ["https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif"],
            'trending': [
                "https://media.giphy.com/media/3o7aCTPPm4OHfRLSH6/giphy.gif",
                "https://media.giphy.com/media/l46Cy1rHbQ92uuLXa/giphy.gif",
                "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif"
            ],
        }
        placeholder_stickers = {
            'hello': ["https://media.giphy.com/media/3o7TKSha51ATTx9KzC/giphy.gif"],
            'happy': ["https://media.giphy.com/media/3o7abAHdYvZdBNnGZq/giphy.gif"],
            'trending': ["https://media.giphy.com/media/3o7TKSha51ATTx9KzC/giphy.gif"],
        }
        data_source = placeholder_stickers if media_type == 'stickers' else placeholder_gifs
        gifs = data_source.get(query, data_source.get('hello', []))
        source = 'local_placeholder'
    
    return JsonResponse({
        "gifs": gifs,
        "type": media_type,
        "count": len(gifs),
        "source": source
    })
