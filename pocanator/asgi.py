"""
ASGI config for POCanator project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pocanator.settings')

application = get_asgi_application()