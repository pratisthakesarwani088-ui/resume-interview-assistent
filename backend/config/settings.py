"""
Django settings for the AI Resume-Based Theory Interview Assistant.
Module 1: Authentication & User Management
Module 2: Resume Upload & Processing
Module 8: Dockerized deployment — Django no longer talks to Gemini directly;
that moved to the FastAPI AI service (see AI_SERVICE_URL below). Production
security, WhiteNoise static files, and DATABASE_URL support were added here
for Render/Docker deployment.
"""

from datetime import timedelta
from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Loads backend/.env for local (non-Docker, non-Render) development. In
# Docker Compose and on Render, real environment variables are injected by
# the platform and this is a harmless no-op if no .env file exists.
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Core / Security
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-secret-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 3rd party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    # local
    "accounts",
    "resumes",
    "analysis",
    "rag",
    "assistant",
    "history",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database (PostgreSQL). Three ways to configure it, checked in order:
#   1. DATABASE_URL — a single connection string. This is what Render's
#      managed Postgres provides automatically, so this is what makes
#      Render deployment "just work" without hand-mapping DB_* vars.
#   2. Individual DB_NAME/DB_USER/... vars — Module 1's original local-dev
#      setup, unchanged, still the default for docker-compose and anyone
#      who prefers explicit vars over a URL.
#   3. USE_SQLITE=True — skips Postgres entirely for a quick local run.
# ---------------------------------------------------------------------------
# if os.environ.get("USE_SQLITE", "False") == "True":
#     DATABASES = {
#         "default": {
#             "ENGINE": "django.db.backends.sqlite3",
#             "NAME": BASE_DIR / "db.sqlite3",
#         }
#     }
# elif os.environ.get("DATABASE_URL"):
#     import dj_database_url

#     DATABASES = {
#         "default": dj_database_url.config(
#             env="DATABASE_URL",
#             conn_max_age=600,
#             ssl_require=os.environ.get("DATABASE_SSL_REQUIRE", "False") == "True",
#         )
#     }
# else:
#     DATABASES = {
#         "default": {
#             "ENGINE": "django.db.backends.postgresql",
#             "NAME": os.environ.get("DB_NAME", "interview_assistant"),
#             "USER": os.environ.get("DB_USER", "postgres"),
#             "PASSWORD": os.environ.get("DB_PASSWORD", "postgres"),
#             "HOST": os.environ.get("DB_HOST", "localhost"),
#             "PORT": os.environ.get("DB_PORT", "5432"),
#         }
#     }

if os.environ.get("USE_SQLITE", "False") == "True":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
elif os.environ.get("DATABASE_URL"):
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.config(
            env="DATABASE_URL",
            conn_max_age=600,
            ssl_require=os.environ.get("DATABASE_SSL_REQUIRE", "False") == "True",
        )
    }
elif os.environ.get("DB_ENGINE", "postgres") == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("DB_NAME", "interview_assistant"),
            "USER": os.environ.get("DB_USER", "root"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "interview_assistant"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", "postgres"),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }

# ---------------------------------------------------------------------------
# Custom user model
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# I18N
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # Manifest storage requires `collectstatic` to have run (done in the
        # Docker build / Render build step) — only used when DEBUG is off,
        # so local `runserver`/`test` without collectstatic still works.
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Media / file uploads (Module 2: resumes)
# ---------------------------------------------------------------------------
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Reasonable cap for a resume PDF. Enforced again in the view/serializer,
# this just stops Django from buffering something absurd into memory first.
MAX_RESUME_SIZE_MB = int(os.environ.get("MAX_RESUME_SIZE_MB", "5"))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_RESUME_SIZE_MB * 1024 * 1024 + (1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_RESUME_SIZE_MB * 1024 * 1024 + (1024 * 1024)

# ---------------------------------------------------------------------------
# AI service (Module 8): FastAPI service that owns all Gemini calls. Django
# no longer talks to Gemini directly — analysis/services.py, assistant/
# services.py, and rag/services.py all call this over HTTP via
# ai_client/client.py. GEMINI_API_KEY etc. now live only in the AI service's
# own environment (see ai_service/.env.example), not here.
# ---------------------------------------------------------------------------
AI_SERVICE_URL = os.environ.get("AI_SERVICE_URL", "http://localhost:8001")
AI_SERVICE_INTERNAL_KEY = os.environ.get("AI_SERVICE_INTERNAL_KEY", "")

# ---------------------------------------------------------------------------
# RAG (Module 4): chunking/storage/retrieval stay in Django — only the
# embedding call moved to the AI service above. ChromaDB itself can be a
# local persistent directory (default, unchanged from Module 4) or a
# networked Chroma server (Module 8's docker-compose/Render setup) when
# CHROMA_HTTP_HOST is set.
# ---------------------------------------------------------------------------
CHROMA_PERSIST_DIR = os.environ.get("CHROMA_PERSIST_DIR") or str(BASE_DIR / "chroma_data")
CHROMA_COLLECTION_NAME = os.environ.get("CHROMA_COLLECTION_NAME") or "resume_chunks"
CHROMA_HTTP_HOST = os.environ.get("CHROMA_HTTP_HOST", "")
CHROMA_HTTP_PORT = int(os.environ.get("CHROMA_HTTP_PORT", "8000"))

# ---------------------------------------------------------------------------
# REST Framework / JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ---------------------------------------------------------------------------
# CORS (React dev server)
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Production security (Module 8). All gated behind `not DEBUG` so local
# development (DEBUG=True) is unaffected — these only take effect once
# DJANGO_DEBUG=False is set, as it should be on Render/production.
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True") == "True"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    # Render (and most PaaS reverse proxies) terminate TLS and forward plain
    # HTTP internally with this header set — without it, Django can't tell
    # the original request was HTTPS and SECURE_SSL_REDIRECT would loop.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
