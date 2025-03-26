"""
WSGI config for Plurium POCanator project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plurium_pocanator.settings')

application = get_wsgi_application()