from django.urls import path
from .api_views import PoCCodeAPIView

urlpatterns = [
    path('pocs/<int:poc_id>/code/', PoCCodeAPIView.as_view(), name='poc_code_api'),
]