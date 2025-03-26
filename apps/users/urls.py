from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('profile/edit/', views.UserProfileEditView.as_view(), name='edit-profile'),
    path('api-key/', views.APIKeyView.as_view(), name='api-key'),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('usage/', views.APIUsageView.as_view(), name='api-usage'),
]