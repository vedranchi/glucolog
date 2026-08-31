from django.urls import path, reverse_lazy
from .views import register_view, login_view, logout_view, user_profile_view
from django.contrib.auth import views as auth_views
from django_ratelimit.decorators import ratelimit

# Password reset sends mail to whatever address is submitted, so an unthrottled
# endpoint is both a quota burn and a way to mail-bomb a third party. Limited by
# IP, and again by target address so one inbox cannot be flooded from rotating
# IPs. Applied to the view function rather than in views.py because this is
# Django's built-in class-based view.
password_reset_view = ratelimit(key="ip", rate="5/h", method="POST", block=True)(
    ratelimit(key="post:email", rate="3/h", method="POST", block=True)(
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        )
    )
)

urlpatterns = [
    path('register/', register_view, name="glucoread-register"),
    path('login/', login_view, name='glucoread-login'),
    path('logout/', logout_view, name="glucoread-logout"),
    path('profile/', user_profile_view, name="user-profile"),
    
    # password reset views
    path('password_reset/', password_reset_view, name='password_reset'),

        path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
    template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),

    path('password_reset_confirm/<uidb64>/<token>/',
    auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete')
        ), 
    name='password_reset_confirm'),

    path('password_reset_complete/', auth_views.PasswordResetCompleteView.as_view(
    template_name='registration/password_reset_complete.html'
    ),
    name='password_reset_complete'),
]

