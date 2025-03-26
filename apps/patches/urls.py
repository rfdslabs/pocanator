from django.urls import path
from . import views

urlpatterns = [
    path('commit/<int:pk>/', views.CommitDetailView.as_view(), name='commit-detail'),
    path('file/<int:pk>/', views.FileChangeDetailView.as_view(), name='file-change-detail'),
    path('visual/<int:advisory_id>/', views.VisualDiffView.as_view(), name='visual-diff'),
]