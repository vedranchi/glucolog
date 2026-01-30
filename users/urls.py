from django.urls import path, reverse_lazy
from .views import register_view, login_view, logout_view
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('register/', register_view, name="glucolog-register"),
    path('login/', login_view, name='glucolog-login'),
    path('logout/', logout_view, name="glucolog-logout"),
    
    
    # password reset views
    path('password_reset/', auth_views.PasswordResetView.as_view(
    template_name='registration/password_reset_form.html',
    email_template_name='registration/password_reset_email.html',
    subject_template_name='registration/password_reset_subject.txt',
    success_url=reverse_lazy('password_reset_done')
    ),
    name='password_reset'),

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

