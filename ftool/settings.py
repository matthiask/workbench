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

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'bootstrap3',

    'ftool',
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
    'accounts.middleware.LoginRequiredMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
