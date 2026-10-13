"""
Django settings for POCanator project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key-for-development-only')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'crispy_forms',
    'crispy_bootstrap5',
    
    # Local apps
    'apps.advisories',
    'apps.analysis',
    'apps.patches',
    'apps.users',
    'apps.pocs',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # For static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'pocanator.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'pocanator.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'data', 'db.sqlite3'),
    }
}

# Skip any migration issues for demo purposes
# Comment this out when migrations are properly set up
MIGRATION_MODULES = {
    'advisories': None,
    'analysis': None,
    'patches': None,
    'pocs': None,
    'users': None,
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# API Keys and External Services
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')

# OpenAI API configuration
OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', None)  # Default to official API
OPENAI_API_TYPE = os.getenv('OPENAI_API_TYPE', None)  # For Azure, etc.
OPENAI_API_VERSION = os.getenv('OPENAI_API_VERSION', None)  # For versioned APIs

# PoC Generation settings
POC_DEFAULT_MODEL = os.getenv('POC_DEFAULT_MODEL', 'gpt-4o')
POC_FALLBACK_MODEL = os.getenv('POC_FALLBACK_MODEL', 'gpt-3.5-turbo')
POC_MAX_TOKENS = int(os.getenv('POC_MAX_TOKENS', 4000))
POC_DEEP_THINKING_TOKENS = int(os.getenv('POC_DEEP_THINKING_TOKENS', 6000))

# HTTP settings (leave these as None by default)
HTTP_PROXY = os.getenv('HTTP_PROXY', None)
HTTPS_PROXY = os.getenv('HTTPS_PROXY', None)

# Rest Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

# Ensure data directory exists
os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)