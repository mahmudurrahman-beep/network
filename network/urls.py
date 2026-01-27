from django.urls import path
from . import views
from django.conf import settings
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", views.index, name="index"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register"),
    path("activate/<str:token>/", views.activate, name="activate"),
    path("edit-profile/", views.edit_profile, name="edit_profile"),
    path("posts", views.all_posts, name="all_posts"),
    path("following", views.following, name="following"),
    path("discover/", views.discover_users, name="discover_users"),
    path("profile/<str:username>", views.profile, name="profile"),
    path("new-post", views.new_post, name="new_post"),
    path("toggle-follow/<str:username>/", views.toggle_follow, name="toggle_follow"),
    path("edit-post/<int:post_id>/", views.edit_post, name="edit_post"),
    path("delete-post/<int:post_id>/", views.delete_post, name="delete_post"),
    path("vote/<int:post_id>/", views.toggle_vote, name="toggle_vote"),
    path("notifications", views.notifications_view, name="notifications"),
    path("api/mark-notifications-read", views.mark_notifications_read, name="mark_notifications_read"),
    # NEW: Notification clearing URLs
    path("clear-notifications/", views.clear_all_notifications, name="clear_notifications"),
    path("mark-notifications-read/", views.mark_all_notifications_read, name="mark_notifications_read"),
    path("delete-notification/<int:notification_id>/", views.delete_notification, name="delete_notification"),
    # END NEW
    path("messages/", views.messages_inbox, name="messages_inbox"),
    path("messages/<str:username>/", views.conversation, name="conversation"),
    path("quick-upload-picture/", views.quick_upload_picture, name="quick_upload_picture"),
    path("delete-message/<int:message_id>/", views.delete_message, name="delete_message"),
    path("delete-conversation/<str:username>/", views.delete_conversation, name="delete_conversation"),
    path("followers/<str:username>/", views.followers_list, name="followers_list"),
    path("following/<str:username>/", views.following_list, name="following_list"),
    path("add-comment/<int:post_id>/", views.add_comment, name="add_comment"),
    path("delete-comment/<int:comment_id>/", views.delete_comment, name="delete_comment"),
    path("edit-comment/<int:comment_id>/", views.edit_comment, name="edit_comment"),
    path("search-gifs/", views.search_gifs, name="search_gifs"),
    path('privacy-settings/', views.privacy_settings, name='privacy_settings'),
    path('unblock/<str:username>/', views.unblock_user, name='unblock_user'),
    path('toggle-block/<str:username>/', views.toggle_block, name='toggle_block'), 
    path('submit-report/', views.submit_report, name='submit_report'), 
    path('post/<int:post_id>/', views.post_detail, name='post_detail'), 
    path('api/check-interaction/<str:username>/', views.check_interaction, name='check_interaction'),
]

# Password Reset URLs (from production)
urlpatterns += [
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
    path("new-post/", views.new_post, name="new_post"),
] 
