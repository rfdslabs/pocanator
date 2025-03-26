"""
ASGI config for Plurium POCanator project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plurium_pocanator.settings')

application = get_asgi_application()