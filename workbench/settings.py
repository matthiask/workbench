import os
import sys
import types
from collections import defaultdict

from django.utils.translation import gettext_lazy as _

import dj_database_url
import dj_email_url
from speckenv import env

from workbench.accounts.features import FEATURES, F


BASE_DIR = os.path.dirname(os.path.dirname(__file__))

SECRET_KEY = env("SECRET_KEY", required=True)
DEBUG = env("DEBUG", default=bool({"runserver", "shell"}.intersection(sys.argv)))
TESTING = env("TESTING", default="test" in sys.argv)
LIVE = env("LIVE", default=False)
ALLOWED_HOSTS = env("ALLOWED_HOSTS", default=[])
ADMINS = MANAGERS = [("Matthias Kestenholz", "mk@feinheit.ch")]
DEFAULT_FROM_EMAIL = SERVER_EMAIL = "workbench@feinheit.ch"
CC = env("CC", default=[row[1] for row in MANAGERS])

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
        "colorfield",
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
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
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
    return os.path.join(BASE_DIR, "conf", "fonts", name)


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
        PDF_CREDIT=(
            "Die Gutschrift wird bis zum %(due)s in Auftrag gegeben."
            " Herzlichen Dank für Ihre Geduld."
        ),
        FONTS={
            "regular": font("ZuricBTLig.ttf"),
            "bold": font("ZuricBTBol.ttf"),
            "italic": font("ZuricBTLigIta.ttf"),
            "bolditalic": font("ZuricBTBolIta.ttf"),
        },
        URL="https://workbench.feinheit.ch",
        FEATURES={
            FEATURES.AWT_WARNING_INDIVIDUAL: F.ALWAYS,
            FEATURES.AWT_WARNING_ALL: F.USER,
            FEATURES.BOOKKEEPING: F.USER,
            FEATURES.BREAKS_NAG: F.ALWAYS,
            FEATURES.CAMPAIGNS: F.ALWAYS,
            FEATURES.COFFEE: F.USER,
            FEATURES.CONTROLLING: F.ALWAYS,
            FEATURES.DEALS: F.ALWAYS,
            FEATURES.EXPENSES: F.NEVER,
            FEATURES.FOREIGN_CURRENCIES: F.NEVER,
            FEATURES.GLASSFROG: F.ALWAYS,
            FEATURES.LABOR_COSTS: F.NEVER,
            FEATURES.LATE_LOGGING: F.USER,
            FEATURES.PLANNING: F.ALWAYS,
            FEATURES.WORKING_TIME_CORRECTION: F.USER,
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
        PDF_CREDIT=(
            "Die Gutschrift wird bis zum %(due)s in Auftrag gegeben."
            " Herzlichen Dank für Ihre Geduld."
        ),
        FONTS={
            "regular": font("HelveticaNeueLight.ttf"),
            "bold": font("HelveticaNeueBold.ttf"),
            "italic": font("HelveticaNeueLightItalic.ttf"),
            "bolditalic": font("HelveticaNeueBoldItalic.ttf"),
        },
        URL="https://workbench.diebruchpiloten.com",
        FEATURES={
            FEATURES.AWT_WARNING_INDIVIDUAL: F.USER,
            FEATURES.AWT_WARNING_ALL: F.USER,
            FEATURES.BOOKKEEPING: F.ALWAYS,
            FEATURES.BREAKS_NAG: F.ALWAYS,
            FEATURES.CAMPAIGNS: F.NEVER,
            FEATURES.COFFEE: F.NEVER,
            FEATURES.CONTROLLING: F.ALWAYS,
            FEATURES.DEALS: F.NEVER,
            FEATURES.EXPENSES: F.ALWAYS,
            FEATURES.FOREIGN_CURRENCIES: F.NEVER,
            FEATURES.GLASSFROG: F.NEVER,
            FEATURES.LABOR_COSTS: F.NEVER,
            FEATURES.LATE_LOGGING: F.ALWAYS,
            FEATURES.PLANNING: F.NEVER,
            FEATURES.WORKING_TIME_CORRECTION: F.ALWAYS,
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
        PDF_CREDIT=(
            "Die Gutschrift wird bis zum %(due)s in Auftrag gegeben."
            " Herzlichen Dank für Ihre Geduld."
        ),
        FONTS={
            "regular": font("HelveticaNeueLight.ttf"),
            "bold": font("HelveticaNeueBold.ttf"),
            "italic": font("HelveticaNeueLightItalic.ttf"),
            "bolditalic": font("HelveticaNeueBoldItalic.ttf"),
        },
        URL="https://workbench.blindflugstudios.com",
        FEATURES={
            FEATURES.AWT_WARNING_INDIVIDUAL: F.USER,
            FEATURES.AWT_WARNING_ALL: F.USER,
            FEATURES.BOOKKEEPING: F.USER,
            FEATURES.BREAKS_NAG: F.NEVER,
            FEATURES.CAMPAIGNS: F.NEVER,
            FEATURES.COFFEE: F.USER,
            FEATURES.CONTROLLING: F.USER,
            FEATURES.DEALS: F.NEVER,
            FEATURES.EXPENSES: F.ALWAYS,
            FEATURES.FOREIGN_CURRENCIES: F.ALWAYS,
            FEATURES.GLASSFROG: F.NEVER,
            FEATURES.LABOR_COSTS: F.USER,
            FEATURES.LATE_LOGGING: F.USER,
            FEATURES.PLANNING: F.NEVER,
            FEATURES.WORKING_TIME_CORRECTION: F.USER,
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
        PDF_CREDIT=(
            "Die Gutschrift wird bis zum %(due)s in Auftrag gegeben."
            " Herzlichen Dank für Ihre Geduld."
        ),
        FONTS={
            "regular": font("ZuricBTLig.ttf"),
            "bold": font("ZuricBTBol.ttf"),
            "italic": font("ZuricBTLigIta.ttf"),
            "bolditalic": font("ZuricBTBolIta.ttf"),
        },
        URL="https://workbench-test.feinheit.ch",
        FEATURES={
            FEATURES.AWT_WARNING_INDIVIDUAL: F.USER,
            FEATURES.AWT_WARNING_ALL: F.USER,
            FEATURES.BOOKKEEPING: F.ALWAYS,
            FEATURES.BREAKS_NAG: F.ALWAYS,
            FEATURES.CAMPAIGNS: F.NEVER,
            FEATURES.COFFEE: F.NEVER,
            FEATURES.CONTROLLING: F.ALWAYS,
            FEATURES.DEALS: F.ALWAYS,
            FEATURES.EXPENSES: F.ALWAYS,
            FEATURES.FOREIGN_CURRENCIES: F.ALWAYS,
            FEATURES.GLASSFROG: F.NEVER,
            FEATURES.LABOR_COSTS: F.ALWAYS,
            FEATURES.LATE_LOGGING: None,
            FEATURES.PLANNING: F.ALWAYS,
            FEATURES.WORKING_TIME_CORRECTION: F.ALWAYS,
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
    FEATURES = defaultdict(lambda: F.ALWAYS, {"LATE_LOGGING": F.USER})
