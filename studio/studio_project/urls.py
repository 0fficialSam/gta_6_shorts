"""
URL configuration for GTA 6 Studio project.
"""
from django.contrib import admin
from django.urls import path
from dashboard import views

urlpatterns = [
    path('', views.index, name='index'),
    path('media/<str:filename>', views.serve_output_file, name='serve_media'),
    path('api/news/', views.api_get_news, name='api_news'),
    path('api/news/refresh/', views.api_refresh_news, name='api_refresh_news'),
    path('api/generate/instagram/', views.api_generate_instagram, name='api_gen_instagram'),
    path('api/generate/video/', views.api_generate_video, name='api_gen_video'),
    path('api/status/', views.api_get_status, name='api_status'),
    path('api/media/', views.api_get_media, name='api_media'),
    path('assets/<str:category>/<path:filepath>', views.serve_asset_file, name='serve_asset'),
    path('api/open-folder/', views.api_open_folder, name='api_open_folder'),
    path('api/screenshots/', views.api_get_screenshots, name='api_screenshots'),
    path('api/music/', views.api_get_music_tracks, name='api_music'),
    path('api/games/', views.api_get_popular_games, name='api_popular_games'),
    path('api/games/fetch-images/', views.api_fetch_game_images, name='api_fetch_game_images'),
    path('api/upload-shot/', views.api_upload_shot, name='api_upload_shot'),
    path('api/match-screenshot/', views.api_match_screenshot, name='api_match_screenshot'),
]

