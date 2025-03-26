from django.urls import path
from . import api_views

urlpatterns = [
    path('advisories/', api_views.AdvisoryListAPIView.as_view(), name='api-advisory-list'),
    path('advisories/<str:github_id>/', api_views.AdvisoryDetailAPIView.as_view(), name='api-advisory-detail'),
    path('advisories/<str:github_id>/commits/', api_views.CommitListAPIView.as_view(), name='api-commit-list'),
    path('advisories/fetch/', api_views.FetchAdvisoryAPIView.as_view(), name='api-fetch-advisory'),
]