from django.urls import path
from . import api_views

urlpatterns = [
    path('analyses/', api_views.AnalysisListAPIView.as_view(), name='api-analysis-list'),
    path('analyses/<int:pk>/', api_views.AnalysisDetailAPIView.as_view(), name='api-analysis-detail'),
    path('advisories/<str:github_id>/analyze/', api_views.CreateAnalysisAPIView.as_view(), name='api-create-analysis'),
    path('analyses/<int:pk>/report/', api_views.AnalysisReportAPIView.as_view(), name='api-analysis-report'),
]