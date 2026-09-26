# syntax=docker/dockerfile:1
#
# Built from the services/ directory, like the other Python services.

# ---- build stage: resolve and install locked dependencies into a venv ----
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /usr/local/bin/uv

# The venv is built at the path it will be used from: a virtualenv is not
# relocatable, so building it elsewhere and copying it yields "no such file or
# directory" about a python that is not there.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app
COPY mcp-storefront/pyproject.toml mcp-storefront/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# ---- runtime stage: only the venv and the application code ----
FROM python:3.13-slim AS runtime

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY mcp-storefront/app ./app

USER 10001:10001
EXPOSE 8000

# One worker per pod: the work is IO-bound and async, so more workers buy
# nothing and multiply the memory. Scale with replicas instead — which is safe
# here because the transport is stateless and no replica holds a session.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
