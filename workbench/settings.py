import os
import sys
import types

from django.utils.translation import gettext_lazy as _

import dj_database_url
from speckenv import env, read_speckenv


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
read_speckenv(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("SECRET_KEY", required=True)
DEBUG = env("DEBUG", default=any(arg in {"runserver"} for arg in sys.argv))
LIVE = env("LIVE", default=False)
ALLOWED_HOSTS = env("ALLOWED_HOSTS", default=[])
ADMINS = MANAGERS = [("Matthias Kestenholz", "mk@feinheit.ch")]
DEFAULT_FROM_EMAIL = SERVER_EMAIL = "workbench@workbench.feinheit.ch"
BCC = env("BCC", default=[row[1] for row in MANAGERS])

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
        "bootstrap4",
        "django_countries",
        "authlib",
        "corsheaders",
        "fineforms",
        "webpack_loader",
        "django.forms",
        "workbench.accounts",
        "workbench.accruals",
        "workbench.activities",
        "workbench.audit",
        "workbench.awt",
        "workbench.circles",
        "workbench.contacts",
        "workbench.credit_control",
        "workbench.deals",
        "workbench.expenses",
        "workbench.invoices",
        "workbench.logbook",
        "workbench.offers",
        "workbench.projects",
        "workbench.services",
        "debug_toolbar" if DEBUG else "",
    ]
    if a
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_REDIRECT_URL = "/"

MIDDLEWARE = [
    m
    for m in [
        "django.middleware.security.SecurityMiddleware" if LIVE else "",
        "debug_toolbar.middleware.DebugToolbarMiddleware" if DEBUG else "",
        "corsheaders.middleware.CorsMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.locale.LocaleMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "workbench.accounts.middleware.user_language",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
        "workbench.accounts.middleware.login_required",
    ]
    if m
]

ROOT_URLCONF = "workbench.urls"
WSGI_APPLICATION = "wsgi.application"
WEBPACK_LOADER = {
    "DEFAULT": {
        "STATS_FILE": os.path.join(
            BASE_DIR, "static", "webpack-stats-%s.json" % ("dev" if DEBUG else "prod")
        )
    }
}

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
                "workbench.context_processors.workbench",
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

AUTHENTICATION_BACKENDS = ["authlib.backends.EmailBackend"]

DATABASES = {"default": dj_database_url.config(default="sqlite:///db.sqlite3")}
ATOMIC_REQUESTS = True

LANGUAGE_CODE = "de"
LANGUAGES = [("en", _("english")), ("de", _("german"))]
TIME_ZONE = "Europe/Zurich"
USE_I18N = True
USE_L10N = False
USE_TZ = True

if LIVE:  # pragma: no cover
    STATICFILES_STORAGE = (
        "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    )
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")

GOOGLE_CLIENT_ID = env("OAUTH2_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = env("OAUTH2_CLIENT_SECRET", default=None)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTOCOL", "https")

SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_HTTPONLY = True
# SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 86400
SESSION_SAVE_EVERY_REQUEST = True

MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"

FINEFORMS_WRAPPERS = {"field": "workbench.wrappers.BootstrapFieldWrapper"}
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"


def font(name):
    return os.path.join(BASE_DIR, "stuff", "fonts", name)


NAMESPACE = env("NAMESPACE", required=True)
WORKBENCH = {
    "feinheit": types.SimpleNamespace(
        SSO_DOMAIN="feinheit.ch",
        PDF_LANGUAGE="de",
        PDF_COMPANY="Feinheit AG",
        PDF_ADDRESS="Feinheit AG · Fabrikstrasse 54 · 8005 Zürich · www.feinheit.ch",
        PDF_VAT_NO="CHE-113.948.417 MWST",
        PDF_OFFER_TERMS=(
            "Bestandteil dieser Offerte sind die zum Zeitpunkt"
            " des Vertragsabschlusses aktuellen Allgemeinen"
            " Geschäftsbedingungen der Feinheit AG."
            " Die jeweils aktuelle Version finden Sie auf www.feinheit.ch/agb/."
        ),
        PDF_INVOICE_PAYMENT=(
            "Wir bedanken uns für die Überweisung des Betrags mit Angabe"
            " der Referenznummer %(code)s bis zum %(due)s"
            " auf ZKB Konto IBAN CH52 0070 0114 8022 0855 1."
        ),
        FONTS={
            "regular": font("ZuricBTLig.ttf"),
            "bold": font("ZuricBTBol.ttf"),
            "italic": font("ZuricBTLigIta.ttf"),
            "bolditalic": font("ZuricBTBolIta.ttf"),
        },
        BACKGROUND="#e3f2fd",
        URL="https://workbench.feinheit.ch",
    ),
    "dbpag": types.SimpleNamespace(
        SSO_DOMAIN="diebruchpiloten.com",
        PDF_LANGUAGE="de",
        PDF_COMPANY="Die Bruchpiloten AG",
        PDF_ADDRESS=(
            "Die Bruchpiloten AG · Fabrikstrasse 54 · 8005 Zürich"
            " · diebruchpiloten.com"
        ),
        PDF_VAT_NO="CHE-239.647.366 MWST",
        PDF_OFFER_TERMS=(
            "Bestandteil dieser Offerte sind die zum Zeitpunkt"
            " des Vertragsabschlusses aktuellen Allgemeinen"
            " Geschäftsbedingungen der Die Bruchpiloten AG."
        ),
        PDF_INVOICE_PAYMENT=(
            "Wir bedanken uns für die Überweisung des Betrags mit Angabe"
            " der Referenznummer %(code)s bis zum %(due)s"
            " auf ZKB Konto IBAN CH78 0070 0110 0070 4877 9."
        ),
        FONTS={
            "regular": font("HelveticaNeueLight.ttf"),
            "bold": font("HelveticaNeueBold.ttf"),
            "italic": font("HelveticaNeueLightItalic.ttf"),
            "bolditalic": font("HelveticaNeueBoldItalic.ttf"),
        },
        BACKGROUND="#dadcab",
        URL="https://dbpag.feinheit.ch",
    ),
}[env("NAMESPACE", required=True)]

SILENCED_SYSTEM_CHECKS = [
    "1_10.W001"  # MIDDLEWARE_CLASSES is not used anymore, thank you.
]

INTERNAL_IPS = ["127.0.0.1"]

if LIVE:  # pragma: no cover
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = "DENY"
    SESSION_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 604800  # One week
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
else:
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


MAILCHIMP_API_KEY = env("MAILCHIMP_API_KEY", warn=True)
MAILCHIMP_LIST_ID = env("MAILCHIMP_LIST_ID", warn=True)
GLASSFROG_TOKEN = env("GLASSFROG_TOKEN", warn=True)
CORS_ORIGIN_WHITELIST = env("CORS_ORIGIN_WHITELIST", default=[])
CORS_ALLOW_CREDENTIALS = True


if DEBUG:  # pragma: no cover
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

if env("SQL", default=False):  # pragma: no cover
    from django.utils.log import DEFAULT_LOGGING as LOGGING

    LOGGING["handlers"]["console"]["level"] = "DEBUG"
    LOGGING["loggers"]["django.db.backends"] = {
        "level": "DEBUG",
        "handlers": ["console"],
        "propagate": False,
    }
