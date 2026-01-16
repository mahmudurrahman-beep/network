import os
import json
import pytz

from django.db import IntegrityError
from django.db.models import Q
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt

from .models import User, Post, PostMedia, Follow, Notification, Message, Comment


def index(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('all_posts'))  
    else:
        return render(request, "network/landing.html")  

def login_view(request):
    if request.method == "POST":
        identifier = request.POST.get("identifier", "").strip()  # renamed from email
        password = request.POST.get("password", "")

        if not identifier or not password:
            return render(request, "network/login.html", {"message": "Email/Username and password required."})

        # Try email first
        user = None
        try:
            user = User.objects.get(email=identifier)
        except User.DoesNotExist:
            # Then try username
            try:
                user = User.objects.get(username=identifier)
            except User.DoesNotExist:
                pass

        if user:
            user = authenticate(request, username=user.username, password=password)  # always use username for auth

            if user is not None:
                if user.is_active:
                    login(request, user)
                    return HttpResponseRedirect(reverse("index"))
                else:
                    return render(request, "network/login.html", {"message": "Account not activated."})

        return render(request, "network/login.html", {"message": "Invalid email/username or password."})

    return render(request, "network/login.html")
    
def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))

def register(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirmation = request.POST.get("confirmation", "")

        # Validation
        if not username:
            return render(request, "network/register.html", {"message": "Username is required."})
        if not email:
            return render(request, "network/register.html", {"message": "Email is required."})
        if not password:
            return render(request, "network/register.html", {"message": "Password is required."})
        if password != confirmation:
            return render(request, "network/register.html", {"message": "Passwords must match."})

        try:
            # Create inactive user
            user = User.objects.create_user(username, email, password)
            user.is_active = False  # Disable until verified

            # Generate activation token
            token = get_random_string(32)
            user.activation_token = token  # Direct on User model
            user.save()

            # Build activation link
            activation_link = request.build_absolute_uri(reverse('activate', args=[token]))

            # Email context for template
            context = {
                'username': username,
                'activation_link': activation_link,
                'email': email,
                'protocol': 'https' if request.is_secure() else 'http',
                'domain': request.get_host(),
            }

            # Render HTML email
            html_message = render_to_string('network/emails/activation_email.html', context)

            # Create plain text fallback
            plain_message = strip_tags(html_message)

            # Send email
            send_mail(
                'Activate Your Network Account',
                plain_message,
                DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
                fail_silently=False,
            )

            # Success
            return render(request, "network/register.html", {
                "message": "Registration successful! Check your email to activate your account."
            })

        except IntegrityError:
            return render(request, "network/register.html", {"message": "Username already taken."})

        except ValueError as e:
            return render(request, "network/register.html", {"message": str(e)})

    # GET request - show form
    return render(request, "network/register.html")
    
# New social features (from our plan)
@login_required
def new_post(request):
    if request.method == "POST":
        content = request.POST.get('content', '').strip()
        if not content:
            return JsonResponse({"error": "Content required"}, status=400)
        
        post = Post.objects.create(user=request.user, content=content)
        
        # Handle media uploads
        for f in request.FILES.getlist('media_files'):
            media_type = 'video' if f.content_type.startswith('video') else 'image'
            PostMedia.objects.create(post=post, file=f, media_type=media_type)
        
        return JsonResponse({"message": "Posted!", "post_id": post.id}, status=201)
    
    return render(request, "network/new_post.html")

@login_required
def all_posts(request):
    posts = Post.objects.all()
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, "network/all_posts.html", {'page_obj': page_obj})

@login_required
def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    posts = profile_user.posts.all()
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

@login_required
def following(request):
    followed_users = request.user.following.values_list('followed_id', flat=True)
    posts = Post.objects.filter(user__id__in=followed_users)
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, "network/following.html", {'page_obj': page_obj})

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
    
    # Return both counts (optional but very useful for live update)
    return JsonResponse({
        "action": action,
        "followers": target_user.followers.count(),
        "following": target_user.following.count()  # optional – if you want to update following count too
    })

@csrf_exempt
@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, user=request.user)  # only own posts

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
    
    if request.user in field.all():
        field.remove(request.user)  # Undo vote
    else:
        opposite.remove(request.user)  # Remove opposite vote if present
        field.add(request.user)
        # Only create notification if the voter is not the post owner
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
    # Mark all as read when viewed (or do via JS on click)
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
        user.bio = request.POST.get('bio', '')
        user.timezone = request.POST.get('timezone', 'UTC')
        user.save()
        return redirect('profile', username=user.username)
    
    # Timezone choices for template
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
                        media_type = 'image'  # default
                
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
def delete_message(request, message_id):
    message = get_object_or_404(Message, id=message_id, sender=request.user)  # only own messages
    
    if request.method == "POST":
        message.delete()
        return JsonResponse({"message": "Message deleted"})
    
    return JsonResponse({"error": "POST required"}, status=400) 

@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == "POST":
        content = request.POST.get('content', '').strip()
        if content:
            Comment.objects.create(user=request.user, post=post, content=content)
            # Optional notification
            if request.user != post.user:
                Notification.objects.create(
                    user=post.user,
                    actor=request.user,
                    verb="commented on your post",
                    post=post
                )
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
    return HttpResponseRedirect('/')

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
    # Get actual User objects who follow profile_user
    followers = User.objects.filter(following__followed=profile_user)
    return render(request, "network/followers_list.html", {
        'profile_user': profile_user,
        'users': followers,
        'list_type': 'Followers'
    })

@login_required
def following_list(request, username):
    profile_user = get_object_or_404(User, username=username)
    # Get actual User objects profile_user follows
    following = User.objects.filter(followers__follower=profile_user)
    return render(request, "network/followers_list.html", {
        'profile_user': profile_user,
        'users': following,
        'list_type': 'Following'
    })

def activate(request, token):
    try:
        user = User.objects.get(activation_token=token)  # Direct on User
        user.is_active = True
        user.activation_token = None
        user.save()
        login(request, user)
        return HttpResponseRedirect(reverse('index'))
    except User.DoesNotExist:
        return render(request, "network/activation_error.html", {
            "message": "Invalid or expired activation link."
        })   

@csrf_exempt
@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, user=request.user)  # Only own
    if request.method == "POST":
        comment.delete()
        return JsonResponse({"message": "Comment deleted"})
    return JsonResponse({"error": "POST required"}, status=400)

@csrf_exempt
@login_required
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, user=request.user)  # Only own

    if request.method == "PUT":
        data = json.loads(request.body)
        new_content = data.get('content', '').strip()
        if new_content:
            comment.content = new_content
            comment.save()
            return JsonResponse({"message": "Comment updated", "content": new_content})
        return JsonResponse({"error": "Content cannot be empty"}, status=400)

    return JsonResponse({"error": "PUT required"}, status=400)
