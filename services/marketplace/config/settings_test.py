"""Settings for the test suite: the real settings plus safe placeholder secrets."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret")
os.environ.setdefault("DB_PASSWORD", "test-only-password")

from config.settings import *  # noqa: E402, F403
