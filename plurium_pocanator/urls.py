"""
URL configuration for Plurium POCanator project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apps.advisories.api_urls')),
    path('api/', include('apps.analysis.api_urls')),
    path('api/', include('apps.pocs.api_urls')),
    path('advisories/', include('apps.advisories.urls')),
    path('analysis/', include('apps.analysis.urls')),
    path('patches/', include('apps.patches.urls')),
    path('accounts/', include('apps.users.urls')),
    path('pocs/', include('apps.pocs.urls')),
    path('', RedirectView.as_view(url='advisories/'), name='home'),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)