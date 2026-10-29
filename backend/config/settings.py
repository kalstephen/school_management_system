"""Django settings for the school management system.

Configuration comes from environment variables so the same code runs in development
(SQLite) and production (PostgreSQL with row-level security).
"""

import os
from pathlib import Path

from django.urls import reverse_lazy

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, str(default)).lower() in {"1", "true", "yes", "on"}


SECRET_KEY = env("SECRET_KEY", "dev-insecure-key-change-me")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "apps.core",
    "apps.accounts",
    "apps.subscriptions",
    "apps.schoolsetup",
    "apps.curriculum",
    "apps.learners",
    "apps.admissions",
    "apps.staff",
    "apps.timetable",
    "apps.attendance",
    "apps.assessment",
    "apps.promotion",
    "apps.discipline",
    "apps.communication",
    "apps.finance",
    "apps.library",
    "apps.sickbay",
    "apps.stores",
    "apps.dashboard",
    "apps.sync",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.SchoolContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
AUTH_USER_MODEL = "accounts.User"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

if env("DB_ENGINE", "sqlite") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "sms"),
            "USER": env("DB_USER", "sms_app"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
            "ATOMIC_REQUESTS": True,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "ATOMIC_REQUESTS": True,
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# SQLite (development) cannot enforce "nulls not distinct" unique constraints; PostgreSQL does.
SILENCED_SYSTEM_CHECKS = ["models.W047"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Africa/Kampala"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True
    if SECRET_KEY == "dev-insecure-key-change-me":
        raise RuntimeError("Set SECRET_KEY in the environment for production.")

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
CORS_ALLOW_CREDENTIALS = True

_mail_backend = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
MAILERS = {
    "default": {
        "BACKEND": _mail_backend,
        "OPTIONS": {
            "host": env("EMAIL_HOST", "localhost"),
            "port": int(env("EMAIL_PORT", "587")),
            "username": env("EMAIL_USER", ""),
            "password": env("EMAIL_PASSWORD", ""),
            "use_tls": env_bool("EMAIL_USE_TLS", True),
        }
        if _mail_backend.endswith("smtp.EmailBackend")
        else {},
    }
}
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@school.local")

# Address of the web app, used in report-card QR codes and emailed links.
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", "http://localhost:5173")

# Failed logins before a temporary lockout, and the lockout length in minutes.
LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_MINUTES = 15

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.exception_handler",
    # The public "Request access" form: a few requests per hour from one address.
    "DEFAULT_THROTTLE_RATES": {"access_request": env("ACCESS_REQUEST_RATE", "5/hour")},
}

SPECTACULAR_SETTINGS = {
    "TITLE": "SPEX School Manager API",
    "DESCRIPTION": "Academics, operations and expenditure for Ugandan schools (no fees).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

UNFOLD = {
    "SITE_TITLE": "SPEX School Manager — Content Manager",
    "SITE_HEADER": "SPEX School Manager",
    "SITE_SYMBOL": "school",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "COLORS": {
        "primary": {  # SPEX Electric Blue (#1E88E5), text shade #1565C0
            "50": "232 243 253",
            "100": "207 230 251",
            "200": "162 205 246",
            "300": "113 178 240",
            "400": "72 156 235",
            "500": "30 136 229",
            "600": "21 101 192",
            "700": "15 79 154",
            "800": "11 59 117",
            "900": "11 31 58",
            "950": "7 21 42",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
    },
    "LOGIN": {"redirect_after": reverse_lazy("admin:index")},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "WARNING")},
}
