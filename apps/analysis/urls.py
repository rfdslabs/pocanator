from django.urls import path
from . import views

urlpatterns = [
    path('', views.AnalysisListView.as_view(), name='analysis-list'),
    path('<int:pk>/', views.AnalysisDetailView.as_view(), name='analysis-detail'),
    path('<int:pk>/report/', views.AnalysisReportView.as_view(), name='analysis-report'),
    path('create/<str:github_id>/', views.CreateAnalysisView.as_view(), name='create-analysis'),
    path('<int:pk>/regenerate/', views.RegenerateAnalysisView.as_view(), name='analysis-regenerate'),
]