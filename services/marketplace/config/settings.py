import base64
from pathlib import Path

from config.env import env_bool, env_int, env_list, env_str

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = env_str("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
]

AUTH_USER_MODEL = "accounts.User"

# Argon2id is the current recommendation for password hashing; the others stay
# so existing hashes can still be verified and upgraded on next login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": env_str("DB_HOST", "localhost"),
        "PORT": env_int("DB_PORT", 5432),
        "NAME": env_str("DB_NAME", "marketplace"),
        "USER": env_str("DB_USER", "marketplace"),
        "PASSWORD": env_str("DB_PASSWORD"),
        # Reuse connections across requests; verify them before reuse.
        "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"connect_timeout": env_int("DB_CONNECT_TIMEOUT", 3)},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Tokens -----------------------------------------------------------------
# Keys are PEM, base64-encoded so they survive a single-line environment
# variable. Only this service holds the private key.
JWT_PRIVATE_KEY = base64.b64decode(env_str("JWT_PRIVATE_KEY_B64")).decode()
JWT_PUBLIC_KEY = base64.b64decode(env_str("JWT_PUBLIC_KEY_B64")).decode()
JWT_KEY_ID = env_str("JWT_KEY_ID", "poshra-2026-09")
JWT_ISSUER = env_str("JWT_ISSUER", "poshra-marketplace")
JWT_AUDIENCE = env_str("JWT_AUDIENCE", "poshra-api")
# Short access token: a stateless token cannot be withdrawn, so its lifetime
# is the blast radius of a stolen one.
JWT_ACCESS_TTL_SECONDS = env_int("JWT_ACCESS_TTL_SECONDS", 600)
JWT_REFRESH_TTL_SECONDS = env_int("JWT_REFRESH_TTL_SECONDS", 60 * 60 * 24 * 14)

# --- Auth cookies -----------------------------------------------------------
ACCESS_COOKIE_NAME = env_str("ACCESS_COOKIE_NAME", "poshra_at")
REFRESH_COOKIE_NAME = env_str("REFRESH_COOKIE_NAME", "poshra_rt")
CSRF_COOKIE_NAME_AUTH = env_str("CSRF_COOKIE_NAME_AUTH", "poshra_csrf")
REFRESH_COOKIE_PATH = env_str("REFRESH_COOKIE_PATH", "/api/marketplace/auth")
# Secure cookies require HTTPS. The LAN cluster is plain HTTP for now, so this
# is configurable; it must be true anywhere real.
AUTH_COOKIE_SECURE = env_bool("AUTH_COOKIE_SECURE", default=True)
