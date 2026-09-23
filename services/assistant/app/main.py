"""HTTP surface for the assistant.

The gateway has already verified the session and set X-User-Id; this service
never parses a token. Every call here costs money, so the route it sits behind
requires a signed-in buyer and is rate limited.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.assistant import Assistant
from app.catalog import CatalogClient
from app.checkout import CheckoutClient
from app.config import Config, ConfigError
from app.llm.gemini import RateLimited
from app.logging import configure_logging

log = logging.getLogger(__name__)

# Enough for a shopping conversation; past this the history is trimmed rather
# than sent, because every turn is re-read by the model and paid for again.
MAX_TURNS = 20
MAX_MESSAGE_CHARS = 2000


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ChatRequest(BaseModel):
    messages: list[Turn] = Field(min_length=1, max_length=MAX_TURNS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(os.environ.get("LOG_LEVEL", "info"))
    try:
        config = Config.load()
    except ConfigError as error:
        # Fail at startup rather than on the first shopper's question.
        raise RuntimeError(str(error)) from error

    app.state.config = config
    app.state.assistant = Assistant(
        config,
        CatalogClient(config.catalog_url, config.request_timeout),
        CheckoutClient(config.checkout_url, config.request_timeout),
    )
    log.info(
        "assistant ready",
        extra={"provider": config.provider, "model": config.model},
    )
    yield


app = FastAPI(title="Poshra assistant", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    # Never touches Anthropic or the catalog: an outage elsewhere must not
    # restart this service.
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    x_user_id: str | None = Header(default=None),
    cookie: str | None = Header(default=None),
) -> JSONResponse:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Sign in to ask the assistant.")

    if body.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="The last message must be yours.")

    assistant: Assistant = request.app.state.assistant
    conversation: list[dict[str, Any]] = [
        {"role": turn.role, "content": turn.content} for turn in body.messages
    ]

    try:
        # The shopper's own session travels with the cart tools, so the
        # assistant acts as them and holds no privilege of its own.
        answer = await assistant.reply(conversation, cookie=cookie or "")
    except RateLimited as error:
        # Being out of quota is not a broken service, and telling someone to
        # wait is a different instruction from telling them it is down.
        log.warning("model rate limited", extra={"error": str(error), "user_id": x_user_id})
        raise HTTPException(
            status_code=429,
            detail="The assistant is busy right now. Try again in a minute.",
        ) from error
    except Exception as error:  # noqa: BLE001
        # The detail goes to the log; the shopper gets nothing about internals.
        log.error("assistant failed", extra={"error": str(error), "user_id": x_user_id})
        raise HTTPException(
            status_code=503, detail="The assistant is unavailable right now."
        ) from error

    log.info(
        "answered",
        extra={
            "user_id": x_user_id,
            "turns": len(conversation),
            "tool_calls": answer["tool_calls"],
            "products": len(answer["products"]),
            "checkout_ready": answer["checkout_ready"],
        },
    )
    return JSONResponse(answer)
