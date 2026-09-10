from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard_index, name='index'),
    path('api/command-palette/', views.command_palette_api, name='command_palette_api'),
]
