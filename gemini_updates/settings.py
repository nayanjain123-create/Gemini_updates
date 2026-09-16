import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-gemini-updates-production-ready-secret-key-2026')

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Custom apps
    'accounts.apps.AccountsConfig',
    'reports.apps.ReportsConfig',
    'compliance.apps.ComplianceConfig',
    'audit.apps.AuditConfig',
    'dashboard.apps.DashboardConfig',
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

try:
    import whitenoise
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
except ImportError:
    pass

ROOT_URLCONF = 'gemini_updates.urls'

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
                'reports.context_processors.notifications_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'gemini_updates.wsgi.application'

# Database
# Using SQLite by default for easy local development, Postgres configurable via DATABASE_URL if needed
import dj_database_url

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

if os.environ.get('DATABASE_URL'):
    DATABASES['default'] = dj_database_url.config(
        conn_max_age=600,
        conn_health_checks=True,
    )


# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 6},
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Auth URLs
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'dashboard:index'
LOGOUT_REDIRECT_URL = 'accounts:login'

# Email Backend (Console for local dev & password reset demo)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# System Current Date Override (Set to None to use actual real-world system date)
CURRENT_DATE_OVERRIDE = None

# Web Push Notifications (VAPID Configuration)
WEBPUSH_VAPID_PUBLIC_KEY = os.environ.get(
    'WEBPUSH_VAPID_PUBLIC_KEY',
    'BBqXlykh3Ipf7gENt5pd-KSzMnD0q6GyfcC5_OwXPqVOzFfuIkSltqKhd3zGSZK-rXiTjyvCWQB9KB6C-tx7ZwM'
)
WEBPUSH_VAPID_PRIVATE_KEY = os.environ.get(
    'WEBPUSH_VAPID_PRIVATE_KEY',
    '''-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg0a3z4FtgYP5Q9MyD
LpetMCKHg/BEm5rFFe9VT+RRKuShRANCAAQal5cpIdyKX+4BDbeaXfikszJw9Kuh
sn3AufzsFz6lTsxX7iJEpbaioXd8xkmSvq14k48rwlkAfSgegvrce2cD
-----END PRIVATE KEY-----'''
)
WEBPUSH_VAPID_ADMIN_EMAIL = os.environ.get('WEBPUSH_VAPID_ADMIN_EMAIL', 'admin@geminiinsights.local')


