from django.urls import path
from . import views

urlpatterns = [
    path('', views.AdvisoryListView.as_view(), name='advisory-list'),
    path('import/', views.ImportAdvisoryView.as_view(), name='import-advisory'),
    path('batch-import/', views.BatchImportView.as_view(), name='batch-import-advisories'),
    path('search/', views.AdvisorySearchView.as_view(), name='search-advisories'),
    # This is a catch-all pattern, so it should be last
    path('<str:github_id>/', views.AdvisoryDetailView.as_view(), name='advisory-detail'),
]
