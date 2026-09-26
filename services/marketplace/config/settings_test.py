"""Settings for the test suite: the real settings plus safe placeholder secrets."""

import base64
import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret")
os.environ.setdefault("DB_PASSWORD", "test-only-password")

# A throwaway key pair per test run: no key material in the repository.
_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
os.environ.setdefault(
    "JWT_PRIVATE_KEY_B64",
    base64.b64encode(
        _key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    ).decode(),
)
os.environ.setdefault(
    "JWT_PUBLIC_KEY_B64",
    base64.b64encode(
        _key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    ).decode(),
)
os.environ.setdefault("AUTH_COOKIE_SECURE", "false")

from config.settings import *  # noqa: E402, F403

# Unit tests use SQLite: fast, no external service. Behaviour against real
# Postgres is covered later by integration tests.
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
# Fast hashing keeps the suite quick; production uses Argon2.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Throttle counters live in a process-wide cache, so dozens of logins across
# the suite would trip the limit and make unrelated tests fail. Throttling is
# exercised deliberately in test_throttling instead.
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {"auth": None, "agent-tokens": None},
}
