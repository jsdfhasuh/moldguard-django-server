import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def env_positive_int(name, default):
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-demo-only-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [
    item.strip() for item in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",") if item.strip()
]
CSRF_TRUSTED_ORIGINS = [
    item.strip() for item in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if item.strip()
]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "apps.common",
    "apps.molds",
    "apps.staff",
    "apps.workorders",
    "apps.analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.common.middleware.RequestIDMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

database_engine = os.getenv("DJANGO_DB_ENGINE", "sqlite").lower()
if database_engine in {"mysql", "mariadb"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DJANGO_DB_NAME", "moldguard"),
            "USER": os.getenv("DJANGO_DB_USER", "moldguard"),
            "PASSWORD": os.getenv("DJANGO_DB_PASSWORD", ""),
            "HOST": os.getenv("DJANGO_DB_HOST", "mariadb"),
            "PORT": os.getenv("DJANGO_DB_PORT", "3306"),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "charset": "utf8mb4",
                "connect_timeout": 10,
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
                "isolation_level": "read committed",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.getenv("DJANGO_DB_PATH", str(BASE_DIR / "db.sqlite3")),
            "OPTIONS": {"timeout": 20},
        }
    }

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = Path(os.getenv("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles")))
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.locmem.EmailBackend").strip()
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost").strip()
EMAIL_PORT = env_positive_int("EMAIL_PORT", 25)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = env_positive_int("EMAIL_TIMEOUT", 15)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "moldguard@localhost").strip()
EMAIL_MESSAGE_ID_DOMAIN = os.getenv("EMAIL_MESSAGE_ID_DOMAIN", "localhost").strip()
MOLDGUARD_REQUIRE_SMTP = env_bool("MOLDGUARD_REQUIRE_SMTP", False)
MOLDGUARD_SMTP_DELIVERY_VERIFIED = env_bool("MOLDGUARD_SMTP_DELIVERY_VERIFIED", False)

if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ValueError("EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be true")
if not DEFAULT_FROM_EMAIL:
    raise ValueError("DEFAULT_FROM_EMAIL must not be empty")
if not re.fullmatch(r"[A-Za-z0-9.-]+", EMAIL_MESSAGE_ID_DOMAIN):
    raise ValueError("EMAIL_MESSAGE_ID_DOMAIN must be a valid message-id domain")
if MOLDGUARD_REQUIRE_SMTP:
    if EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend":
        raise ValueError("Competition deployment requires Django's SMTP email backend")
    if EMAIL_HOST.lower() in {"", "localhost", "smtp.example.com"}:
        raise ValueError("Competition deployment requires a real EMAIL_HOST")
    if "example.com" in DEFAULT_FROM_EMAIL.lower():
        raise ValueError("Competition deployment requires a real DEFAULT_FROM_EMAIL")
    if EMAIL_MESSAGE_ID_DOMAIN.lower() in {
        "localhost",
        "example.com",
    } or EMAIL_MESSAGE_ID_DOMAIN.lower().endswith(".example.com"):
        raise ValueError("Competition deployment requires a real EMAIL_MESSAGE_ID_DOMAIN")
elif MOLDGUARD_SMTP_DELIVERY_VERIFIED:
    raise ValueError("MOLDGUARD_SMTP_DELIVERY_VERIFIED requires MOLDGUARD_REQUIRE_SMTP=true")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.exception_handler",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "MoldGuard Competition Server API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "moldguard.requests": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "moldguard.errors": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "moldguard.email": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

MOLDGUARD_PUBLIC_BASE_URL = os.getenv("MOLDGUARD_PUBLIC_BASE_URL", "http://127.0.0.1:18080").rstrip(
    "/"
)
MOLDGUARD_KNOWLEDGE_VERSION = os.getenv("MOLDGUARD_KNOWLEDGE_VERSION", "MOLDGUARD-KB-1.2")
MOLDGUARD_REPORT_SCHEMA_VERSION = os.getenv("MOLDGUARD_REPORT_SCHEMA_VERSION", "REPORT-FORM-1.1")
MOLDGUARD_ABNORMAL_OVERDUE_HOURS = int(os.getenv("MOLDGUARD_ABNORMAL_OVERDUE_HOURS", "4"))
