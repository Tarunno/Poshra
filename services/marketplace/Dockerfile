# syntax=docker/dockerfile:1

# ---- build stage: resolve and install locked dependencies into a venv ----
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# ---- runtime stage: only the venv and the application code ----
FROM python:3.13-slim AS runtime

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home app

# HOME=/tmp: the runtime user has no home directory, and the root filesystem is
# read-only in Kubernetes, while gunicorn writes runtime files under $HOME.
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
# Whole source tree; .dockerignore keeps tests, caches and .env out, so new
# Django apps do not need a Dockerfile change.
COPY . .

# Numeric UID: Kubernetes cannot verify a user *name* is non-root when
# runAsNonRoot is set.
USER 10001:10001
EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--graceful-timeout", "20"]
