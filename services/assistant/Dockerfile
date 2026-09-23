# syntax=docker/dockerfile:1
#
# Built from the services/ directory, like the other Python service.
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
WORKDIR /src/assistant

COPY assistant/pyproject.toml assistant/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

FROM python:3.13-slim AS runtime

# A numeric user: Kubernetes cannot verify runAsNonRoot for a named one.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin poshra

WORKDIR /app
COPY --from=builder /src/assistant/.venv /app/.venv
COPY assistant/app ./app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER 10001:10001
EXPOSE 8000

# One worker per pod: concurrency here is IO-bound and async, so more workers
# buy nothing and multiply the memory. Scale with replicas instead.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
