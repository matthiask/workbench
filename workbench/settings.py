import os
import sys
import types
from collections import defaultdict

from django.utils.translation import gettext_lazy as _

import dj_database_url
import dj_email_url
from speckenv import env


BASE_DIR = os.path.dirname(os.path.dirname(__file__))

SECRET_KEY = env("SECRET_KEY", required=True)
DEBUG = env("DEBUG", default=bool({"runserver"}.intersection(sys.argv)))
TESTING = env("TESTING", default="test" in sys.argv)
LIVE = env("LIVE", default=False)
ALLOWED_HOSTS = env("ALLOWED_HOSTS", default=[])
ADMINS = MANAGERS = [("Matthias Kestenholz", "mk@feinheit.ch")]
DEFAULT_FROM_EMAIL = SERVER_EMAIL = "workbench@workbench.feinheit.ch"
BCC = env("BCC", default=[row[1] for row in MANAGERS])

DEBUG_TOOLBAR = DEBUG and not TESTING

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
        "workbench.audit",
        "workbench.awt",
        "workbench.circles",
        "workbench.contacts",
        "workbench.credit_control",
        "workbench.deals",
        "workbench.expenses",
        "workbench.invoices",
        "workbench.logbook",
        "workbench.notes",
        "workbench.offers",
        "workbench.planning",
        "workbench.projects",
        "workbench.reporting",
        "workbench.services",
        "workbench.timer",
        "debug_toolbar" if DEBUG_TOOLBAR else "",
    ]
    if a
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_REDIRECT_URL = "/"
LOGIN_REQUIRED_EXEMPT = (
    "/accounts",
    "/favicon",
    "/robots",
    "/sitemap",
    "/create-timestamp",
    "/list-timestamps",
    "/timestamps-controller",
)

MIDDLEWARE = [
    m
    for m in [
        "django.middleware.security.SecurityMiddleware" if LIVE else "",
        "debug_toolbar.middleware.DebugToolbarMiddleware" if DEBUG_TOOLBAR else "",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.locale.LocaleMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
        "workbench.accounts.middleware.user_middleware",
        "workbench.middleware.history_fallback",
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

LOCALE_PATHS = [os.path.join(BASE_DIR, "conf", "locale")]

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
SESSION_COOKIE_AGE = 3 * 86400
SESSION_SAVE_EVERY_REQUEST = True

MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"

FINEFORMS_WRAPPERS = {"field": "workbench.wrappers.BootstrapFieldWrapper"}
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"


def font(name):
    return os.path.join(BASE_DIR, "stuff", "fonts", name)


NAMESPACE = env("NAMESPACE", required=True)
WORKBENCH = {
    "feinheit": types.SimpleNamespace(
        TITLE="Feinheit",
        SSO_DOMAIN="feinheit.ch",
        CURRENCY="CHF",
        PDF_LANGUAGE="de",
        PDF_COMPANY="Feinheit AG",
        PDF_ADDRESS=" · ".join(
            [
                "Feinheit AG",
                "Fabrikstrasse 54, 8005 Zürich",
                "Effingerstrasse 2, 3011 Bern",
                "www.feinheit.ch",
            ]
        ),
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
        URL="https://workbench.feinheit.ch",
        FEATURES={
            "bookkeeping": {"jg@feinheit.ch", "mk@feinheit.ch"},
            "campaigns": True,
            "controlling": True,
            "deals": True,
            "foreign_currencies": False,
            "glassfrog": True,
            "labor_costs": False,
            "planning": True,
            "skip_breaks": False,
            "working_time_correction": {"jg@feinheit.ch", "mk@feinheit.ch"},
        },
        READ_WRITE_ADMIN=False,
    ),
    "dbpag": types.SimpleNamespace(
        TITLE="DBAG",
        SSO_DOMAIN="diebruchpiloten.com",
        CURRENCY="CHF",
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
        URL="https://workbench.diebruchpiloten.com",
        FEATURES={
            "bookkeeping": True,
            "campaigns": False,
            "controlling": True,
            "deals": False,
            "foreign_currencies": False,
            "glassfrog": False,
            "labor_costs": False,
            "planning": False,
            "skip_breaks": False,
            "working_time_correction": True,
        },
        READ_WRITE_ADMIN=False,
    ),
    "bf": types.SimpleNamespace(
        TITLE="Blindflug",
        SSO_DOMAIN="blindflugstudios.com",
        CURRENCY="CHF",
        PDF_LANGUAGE="de",
        PDF_COMPANY="Blindflug Studios AG",
        PDF_ADDRESS=(
            "Blindflug Studios AG · Fabrikstrasse 54 · 8005 Zürich"
            " · blindflugstudios.com"
        ),
        PDF_VAT_NO="CHE-155.657.233 MWST",
        PDF_OFFER_TERMS=(
            "Bestandteil dieser Offerte sind die zum Zeitpunkt"
            " des Vertragsabschlusses aktuellen Allgemeinen"
            " Geschäftsbedingungen der Blindflug Studios AG."
        ),
        PDF_INVOICE_PAYMENT=(
            "Wir bedanken uns für die Überweisung des Betrags mit Angabe"
            " der Referenznummer %(code)s bis zum %(due)s"
            " auf Konto IBAN CH31 0687 7705 0560 9509 7 bei der"
            " Zürcher Landbank AG."
        ),
        FONTS={
            "regular": font("HelveticaNeueLight.ttf"),
            "bold": font("HelveticaNeueBold.ttf"),
            "italic": font("HelveticaNeueLightItalic.ttf"),
            "bolditalic": font("HelveticaNeueBoldItalic.ttf"),
        },
        URL="https://workbench.blindflugstudios.com",
        FEATURES={
            "bookkeeping": {
                "moritz@blindflugstudios.com",
                "jeremy@blindflugstudios.com",
                "frederic@blindflugstudios.com",
                "mk@feinheit.ch",
            },
            "campaigns": False,
            "controlling": {
                "moritz@blindflugstudios.com",
                "jeremy@blindflugstudios.com",
                "frederic@blindflugstudios.com",
                "mk@feinheit.ch",
            },
            "deals": False,
            "foreign_currencies": True,
            "glassfrog": False,
            "labor_costs": {
                "moritz@blindflugstudios.com",
                "jeremy@blindflugstudios.com",
                "frederic@blindflugstudios.com",
                "mk@feinheit.ch",
            },
            "planning": True,
            "skip_breaks": True,  # For now
            "working_time_correction": {
                "moritz@blindflugstudios.com",
                "jeremy@blindflugstudios.com",
                "frederic@blindflugstudios.com",
                "mk@feinheit.ch",
            },
        },
        READ_WRITE_ADMIN=True,
    ),
    "test": types.SimpleNamespace(
        TITLE="Test",
        SSO_DOMAIN="feinheit.ch",
        CURRENCY="CHF",
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
        URL="https://workbench-test.feinheit.ch",
        FEATURES={
            "bookkeeping": True,
            "campaigns": False,
            "controlling": True,
            "deals": True,
            "foreign_currencies": True,
            "glassfrog": False,
            "labor_costs": True,
            "planning": True,
            "skip_breaks": False,
            "working_time_correction": True,
        },
        READ_WRITE_ADMIN=False,
    ),
}[env("NAMESPACE", required=True)]

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
    SECURE_REDIRECT_EXEMPT = [r"^(create-timestamp|list-timestamps)/"]
else:
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    WORKBENCH.TITLE = "(debug) {}".format(WORKBENCH.TITLE)

MAILCHIMP_API_KEY = env("MAILCHIMP_API_KEY", warn=True)
MAILCHIMP_LIST_ID = env("MAILCHIMP_LIST_ID", warn=True)
GLASSFROG_TOKEN = env("GLASSFROG_TOKEN", warn=True)

# Fine since it's only used for selected views
CORS_ORIGIN_ALLOW_ALL = True

if DEBUG:  # pragma: no cover
    globals().update(dj_email_url.parse(env("EMAIL_URL", default="console:")))
else:  # pragma: no cover
    globals().update(dj_email_url.parse(env("EMAIL_URL", default="smtp:", warn=True)))

if env("SQL", default=False):  # pragma: no cover
    from django.utils.log import DEFAULT_LOGGING as LOGGING

    LOGGING["handlers"]["console"]["level"] = "DEBUG"
    LOGGING["loggers"]["django.db.backends"] = {
        "level": "DEBUG",
        "handlers": ["console"],
        "propagate": False,
    }

FEATURES = WORKBENCH.FEATURES
TEST_RUNNER = "django_slowtests.testrunner.DiscoverSlowestTestsRunner"
TESTS_REPORT_TMP_FILES_PREFIX = "tmp/slowtests_"
NUM_SLOW_TESTS = 20

BATCH_MAX_ITEMS = 250

if TESTING:  # pragma: no cover
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    DATABASES["default"]["TEST"] = {"SERIALIZE": False}
    FEATURES = defaultdict(lambda: True)
