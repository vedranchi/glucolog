from django.urls import path
from django.contrib import admin
from . import views

urlpatterns = [
  path('', views.dashboard, name='glucolog-dashboard'),
  path('preferences', views.preferences, name='user-preferences'),
]