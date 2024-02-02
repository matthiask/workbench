"""
Django settings for workbench project.

For more information on this file, see
https://docs.djangoproject.com/en/1.7/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.7/ref/settings/
"""

import os
import sys

import dj_database_url
import dj_email_url
from speckenv import env, read_speckenv


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
read_speckenv(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("SECRET_KEY", required=True)
DEBUG = any(arg == "runserver" for arg in sys.argv)
TESTING = any(arg == "test" for arg in sys.argv)
LIVE = env("LIVE", default=False)
ALLOWED_HOSTS = env("ALLOWED_HOSTS", default=[])
ADMINS = (("Matthias Kestenholz", "mk@feinheit.ch"),)
CANONICAL_DOMAIN = env("CANONICAL_DOMAIN", default=None)
CANONICAL_DOMAIN_SECURE = env("CANONICAL_DOMAIN_SECURE", default=False)
DEFAULT_FROM_EMAIL = "no-reply@hangar.diebruchpiloten.com"
SERVER_EMAIL = "no-reply@hangar.diebruchpiloten.com"

INSTALLED_APPS = [
    a
    for a in [
        "workbench",
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
        "django.contrib.postgres",
        "admin_ordering",
        "bootstrap3",
        "workbench.accounts",
        "workbench.audit",
        "workbench.calendar",
        "debug_toolbar" if DEBUG else "",
    ]
    if a
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_REDIRECT_URL = "/"

MIDDLEWARE = [
    m
    for m in [
        "canonical_domain.middleware.CanonicalDomainMiddleware" if LIVE else "",
        "debug_toolbar.middleware.DebugToolbarMiddleware" if DEBUG else "",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
        "workbench.accounts.middleware.login_required",
    ]
    if m
]

ROOT_URLCONF = "workbench.urls"
WSGI_APPLICATION = "wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "workbench", "templates")],
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "workbench.calendar.context_processors.app",
            ],
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ]
            if DEBUG
            else [
                (
                    "django.template.loaders.cached.Loader",
                    [
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                    ],
                )
            ],
            "debug": DEBUG,
        },
    }
]

LOCALE_PATHS = (os.path.join(BASE_DIR, "conf", "locale"),)

AUTHENTICATION_BACKENDS = ["workbench.accounts.backends.AuthBackend"]

DATABASES = {"default": dj_database_url.config(default="sqlite:///db.sqlite3")}
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

LANGUAGE_CODE = "de-ch"
TIME_ZONE = "Europe/Zurich"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")
if not TESTING:
    STATICFILES_STORAGE = (
        "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    )

OAUTH2_CLIENT_ID = env("OAUTH2_CLIENT_ID", default="")
OAUTH2_CLIENT_SECRET = env("OAUTH2_CLIENT_SECRET", default=None)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTOCOL", "https")

SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_HTTPONLY = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = 30 * 86400

MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"

BOOTSTRAP3 = {
    "horizontal_label_class": "col-md-3",
    "horizontal_field_class": "col-md-9",
}


def font(name):
    return os.path.join(BASE_DIR, "stuff", "fonts", name)


INTERNAL_IPS = ["127.0.0.1"]

if LIVE:
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    X_FRAME_OPTIONS = "DENY"
    SESSION_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_SSL_REDIRECT = True
    # SECURE_HSTS_SECONDS = 604800  # One week
    # SECURE_HSTS_INCLUDE_SUBDOMAINS = True

if DEBUG:
    globals().update(dj_email_url.config(default="console:"))
else:
    globals().update(dj_email_url.config())
