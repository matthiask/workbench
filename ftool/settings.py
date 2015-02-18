"""
Django settings for ftool project.

For more information on this file, see
https://docs.djangoproject.com/en/1.7/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.7/ref/settings/
"""

import dj_database_url
import env
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
env.read_dotenv()

SECRET_KEY = env.env('SECRET_KEY', required=True)
DEBUG = any(arg in ('runserver',) for arg in sys.argv)
TEMPLATE_DEBUG = DEBUG
ALLOWED_HOSTS = env.env('ALLOWED_HOSTS', default=[])
ADMINS = (
    ('Matthias Kestenholz', 'mk@feinheit.ch'),
)

INSTALLED_APPS = (
    'ftool',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'bootstrap3',
    'reversion',

    'accounts',
    'contacts',
    'deals',
    'projects',
    'services',
    'stories',
)

AUTH_USER_MODEL = 'accounts.User'
LOGIN_REDIRECT_URL = '/'

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'reversion.middleware.RevisionMiddleware',
    'accounts.middleware.LoginRequiredMiddleware',
)

ROOT_URLCONF = 'ftool.urls'
WSGI_APPLICATION = 'wsgi.application'

TEMPLATE_DIRS = (
    os.path.join(BASE_DIR, 'templates'),
)
LOCALE_PATHS = (
    os.path.join(BASE_DIR, 'conf', 'locale'),
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.request',
    'django.core.context_processors.static',
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
)

AUTHENTICATION_BACKENDS = (
    'accounts.backends.AuthBackend',
)

# Database
# https://docs.djangoproject.com/en/1.7/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(default='sqlite:///db.sqlite3'),
}

LANGUAGE_CODE = 'de-ch'
TIME_ZONE = 'Europe/Zurich'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

OAUTH2_CLIENT_ID = env.env('OAUTH2_CLIENT_ID', default='')
OAUTH2_CLIENT_SECRET = env.env('OAUTH2_CLIENT_SECRET', default=None)

SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
SESSION_COOKIE_HTTPONLY = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 86400
# SESSION_COOKIE_SECURE = True

BOOTSTRAP3 = {
    'horizontal_label_class': 'col-md-3',
    'horizontal_field_class': 'col-md-9',
}
