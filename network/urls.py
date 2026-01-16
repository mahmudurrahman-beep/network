from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views


urlpatterns = [
    # Main pages
    path("", views.index, name="index"),
    path("posts", views.all_posts, name="all_posts"),
    path("following", views.following, name="following"),
    path("discover/", views.discover_users, name="discover_users"),
    
    # Authentication
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register"),
    path("activate/<str:token>/", views.activate, name="activate"),
    
    # Profile
    path("profile/<str:username>", views.profile, name="profile"),
    path("edit-profile/", views.edit_profile, name="edit_profile"),
    path("quick-upload-picture/", views.quick_upload_picture, name="quick_upload_picture"),
    path("followers/<str:username>/", views.followers_list, name="followers_list"),
    path("following/<str:username>/", views.following_list, name="following_list"),
    
    # Posts
    path("new-post", views.new_post, name="new_post"),
    path("edit-post/<int:post_id>/", views.edit_post, name="edit_post"),
    path("delete-post/<int:post_id>/", views.delete_post, name="delete_post"),
    path("vote/<int:post_id>/", views.toggle_vote, name="toggle_vote"),
    path("add-comment/<int:post_id>/", views.add_comment, name="add_comment"),
    
    # Social interactions
    path("toggle-follow/<str:username>/", views.toggle_follow, name="toggle_follow"),
    
    # Notifications
    path("notifications", views.notifications_view, name="notifications"),
    path("api/mark-notifications-read", views.mark_notifications_read, name="mark_notifications_read"),
    
    # Messages
    path("messages/", views.messages_inbox, name="messages_inbox"),
    path("messages/<str:username>/", views.conversation, name="conversation"),
    path("delete-message/<int:message_id>/", views.delete_message, name="delete_message"),
    path("delete-conversation/<str:username>/", views.delete_conversation, name="delete_conversation"),
]

# Password Reset URLs
password_reset_urls = [
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='network/password_reset.html',
        email_template_name='network/emails/password_reset_email.html',
        html_email_template_name='network/emails/password_reset_email.html',
        subject_template_name='network/password_reset_subject.txt',
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='network/password_reset_done.html'
    ), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='network/password_reset_confirm.html'
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='network/password_reset_complete.html'
    ), name='password_reset_complete'),
]

urlpatterns += password_reset_urls

# Media files (only in DEBUG mode)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
