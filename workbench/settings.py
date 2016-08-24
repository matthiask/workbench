"""
Django settings for workbench project.

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
LIVE = env.env('LIVE', default=False)
ALLOWED_HOSTS = env.env('ALLOWED_HOSTS', default=[])
ADMINS = (
    ('Matthias Kestenholz', 'mk@feinheit.ch'),
)

INSTALLED_APPS = (
    'workbench',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'bootstrap3',

    'accounts',
    'activities',
    'audit',
    'contacts',
    'deals',
    'invoices',
    'offers',
    'projects',
    'services',
    'stories',

    'debug_toolbar',
)

AUTH_USER_MODEL = 'accounts.User'
LOGIN_REDIRECT_URL = '/'

MIDDLEWARE = (
    # 'django.middleware.security.SecurityMiddleware',  # Revisit when SSLing.
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.login_required',
)

ROOT_URLCONF = 'workbench.urls'
WSGI_APPLICATION = 'wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'workbench', 'templates'),
        ],
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

LOCALE_PATHS = (
    os.path.join(BASE_DIR, 'conf', 'locale'),
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

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTOCOL', 'https')

SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
SESSION_COOKIE_HTTPONLY = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 86400
if not DEBUG:
    SESSION_COOKIE_SECURE = True

MESSAGE_STORAGE = 'django.contrib.messages.storage.cookie.CookieStorage'

BOOTSTRAP3 = {
    'horizontal_label_class': 'col-md-3',
    'horizontal_field_class': 'col-md-9',
}

FONTS = {
    'regular': os.path.join(BASE_DIR, 'stuff', 'fonts', 'Lato-Light.ttf'),
    'bold': os.path.join(BASE_DIR, 'stuff', 'fonts', 'Lato-Semibold.ttf'),
    'italic': os.path.join(BASE_DIR, 'stuff', 'fonts', 'Lato-LightItalic.ttf'),
    'bolditalic': os.path.join(BASE_DIR, 'stuff', 'fonts', 'Lato-Bold.ttf'),
}

WORKBENCH_SSO_DOMAIN = 'feinheit.ch'
WORKBENCH_PDF_COMPANY = 'FEINHEIT GmbH'
WORKBENCH_PDF_ADDRESS = 'FEINHEIT GmbH · Molkenstrasse 21 · 8004 Zürich'
WORKBENCH_PDF_VAT_NO = 'CHE-113.948.417 MWST'
WORKBENCH_PDF_OFFER_TERMS = [
    'Bestandteil dieser Offerte sind die zum Zeitpunkt'
    ' des Vertragsabschlusses aktuellen Allgemeinen'
    ' Geschäftsbedingungen der FEINHEIT GmbH.',
    'Die jeweils aktuelle Version'
    ' finden Sie auf www.feinheit.ch/agb/.',
]
WORKBENCH_PDF_INVOICE_PAYMENT = (
    'Wir bedanken uns für die Überweisung des Betrags mit Angabe'
    ' der Referenznummer %(code)s innerhalb von %(days)s Tagen'
    ' (%(due)s) auf Postkonto 85-206645-2'
    ' / IBAN CH50 0900 0000 8520 6645 2.'
)

SILENCED_SYSTEM_CHECKS = [
    '1_10.W001',  # MIDDLEWARE_CLASSES is not used anymore, thank you.
]

if DEBUG:
    MIDDLEWARE += ('workbench.middleware.WorkingDebugToolbarMiddleware',)
    INTERNAL_IPS = ['127.0.0.1']

if LIVE:
    MIDDLEWARE = (
        'django.middleware.security.SecurityMiddleware',
    ) + MIDDLEWARE
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    X_FRAME_OPTIONS = 'DENY'
