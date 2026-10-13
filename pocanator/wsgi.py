"""
WSGI config for POCanator project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pocanator.settings')

application = get_wsgi_application()