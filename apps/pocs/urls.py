from django.urls import path
from . import views

urlpatterns = [
    path('', views.PoCListView.as_view(), name='poc_list'),
    path('request/<int:analysis_id>/', views.request_poc, name='request_poc'),
    path('status/<int:poc_id>/', views.poc_status, name='poc_status'),
    path('status/<int:poc_id>/api/', views.poc_status_api, name='poc_status_api'),
    path('view/<int:poc_id>/', views.view_poc, name='view_poc'),
    path('feedback/<int:poc_id>/', views.poc_feedback, name='poc_feedback'),
    path('regenerate/<int:poc_id>/', views.regenerate_poc, name='regenerate_poc'),
    path('delete/<int:poc_id>/', views.delete_poc, name='delete_poc'),
    path('history/<int:poc_id>/', views.poc_history, name='poc_history'),
]