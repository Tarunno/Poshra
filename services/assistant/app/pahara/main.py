"""Pahara's HTTP surface.

Its own application, deployed separately from the shopping assistant even
though it is built from the same image. They share the model seam — one
provider, one rotation, one set of retries, already tested — and share nothing
else: different route, different network policy, different tools. The shopper's
assistant has no way to read the cluster's telemetry, and Pahara has no way to
touch a cart.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import Config, ConfigError
from app.llm import build_provider
from app.llm.gemini import RateLimited
from app.logging import configure_logging
from app.pahara.agent import Pahara
from app.pahara.observatory import Observatory
from app.telemetry import configure_tracing, tracer

log = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 1000


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=MAX_QUESTION_CHARS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(os.environ.get("LOG_LEVEL", "info"))
    try:
        config = Config.load()
    except ConfigError as error:
        raise RuntimeError(str(error)) from error

    observatory = Observatory(
        tempo=_require("TEMPO_URL"),
        loki=_require("LOKI_URL"),
        prometheus=_require("PROMETHEUS_URL"),
        # Longer than the catalogue's: a TraceQL search over an hour of traces
        # is not a primary key lookup.
        timeout=float(os.environ.get("OBSERVATORY_TIMEOUT", "20")),
    )
    app.state.pahara = Pahara(
        build_provider(config),
        observatory,
        budget=float(os.environ.get("PAHARA_BUDGET", "60")),
    )
    configure_tracing("pahara", app)
    log.info(
        "pahara ready", extra={"provider": config.provider, "models": ", ".join(config.models)}
    )
    yield


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value.rstrip("/")


app = FastAPI(title="Pahara", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/explain")
async def explain(
    request: Request,
    body: Question,
    x_user_id: str | None = Header(default=None),
) -> JSONResponse:
    """Ask what the cluster has been doing.

    Behind the gateway's identity check like everything else: reading the
    telemetry means reading what every shopper did, which is not public.
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Sign in to ask Pahara.")

    pahara: Pahara = request.app.state.pahara
    try:
        with tracer().start_as_current_span("pahara.explain") as span:
            span.set_attribute("poshra.question_chars", len(body.question))
            answered = await pahara.explain(body.question)
            # How many times it looked, and at what: the difference between an
            # answer and a guess, recorded where an operator can see it.
            span.set_attribute("poshra.looks", answered["looks"])
    except RateLimited as error:
        log.warning("model rate limited", extra={"error": str(error)})
        raise HTTPException(
            status_code=429, detail="Every model is busy. Try again in a minute."
        ) from error
    except Exception as error:  # noqa: BLE001
        log.error("pahara failed", extra={"error": str(error)})
        raise HTTPException(status_code=503, detail="Pahara is unavailable right now.") from error

    log.info("explained", extra={"user_id": x_user_id, "looks": answered["looks"]})
    return JSONResponse(answered)
