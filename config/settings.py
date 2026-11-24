"""
Django settings for HostelX project.
Smart Hostel Room Exchange and Hostel Management Platform
"""

import os
import urllib.parse as urlparse
from pathlib import Path
from decimal import Decimal
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-hostelx-smart-exchange-management-platform-key-2026')

DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't')

allowed_hosts_str = os.getenv('ALLOWED_HOSTS', '*')
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_str.split(',') if h.strip()] if allowed_hosts_str != '*' else ['*']

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # HostelX core apps
    'accounts.apps.AccountsConfig',
    'hostels.apps.HostelsConfig',
    'rooms.apps.RoomsConfig',
    'students.apps.StudentsConfig',
    'allocations.apps.AllocationsConfig',
    'exchanges.apps.ExchangesConfig',
    'approvals.apps.ApprovalsConfig',
    'finance.apps.FinanceConfig',
    'notifications.apps.NotificationsConfig',
    'reports.apps.ReportsConfig',
    'audit.apps.AuditConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'notifications.context_processors.unread_notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database Configuration: PostgreSQL (Default) with Environment / SQLite fallback
DATABASE_URL = os.getenv('DATABASE_URL')
DATABASE_ENGINE = os.getenv('DATABASE_ENGINE', 'django.db.backends.postgresql')

if DATABASE_URL:
    url = urlparse.urlparse(DATABASE_URL)
    engine = 'django.db.backends.postgresql'
    if url.scheme in ('postgres', 'postgresql', 'pgsql'):
        engine = 'django.db.backends.postgresql'
    elif url.scheme == 'sqlite':
        engine = 'django.db.backends.sqlite3'

    DATABASES = {
        'default': {
            'ENGINE': engine,
            'NAME': url.path.lstrip('/') if engine != 'django.db.backends.sqlite3' else BASE_DIR / url.path.lstrip('/'),
            'USER': url.username or '',
            'PASSWORD': url.password or '',
            'HOST': url.hostname or '',
            'PORT': str(url.port or 5432) if engine != 'django.db.backends.sqlite3' else '',
        }
    }
elif DATABASE_ENGINE == 'django.db.backends.sqlite3' or os.getenv('USE_SQLITE', 'False').lower() in ('true', '1', 't'):
    sqlite_name = os.getenv('DATABASE_NAME', 'db.sqlite3')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / sqlite_name if not Path(sqlite_name).is_absolute() else Path(sqlite_name),
            'OPTIONS': {
                'timeout': 30,  # 30s busy timeout for concurrent access handling
            }
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DATABASE_NAME', 'hostel_db'),
            'USER': os.getenv('DATABASE_USER', 'postgres'),
            'PASSWORD': os.getenv('DATABASE_PASSWORD', ''),
            'HOST': os.getenv('DATABASE_HOST', 'localhost'),
            'PORT': os.getenv('DATABASE_PORT', '5432'),
            'OPTIONS': {
                'connect_timeout': int(os.getenv('DATABASE_CONNECT_TIMEOUT', '10')),
            }
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 6,
        }
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Console email backend for local notifications
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@hostelx.university.edu'
