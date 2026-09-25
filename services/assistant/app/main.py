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

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.assistant import Assistant
from app.catalog import CatalogClient
from app.checkout import CheckoutClient
from app.config import Config, ConfigError
from app.listing import CannotHearHer, ListingDrafter, NothingToDraftFrom
from app.llm.base import Photograph, Recording
from app.llm.gemini import DraftFailed, RateLimited
from app.logging import configure_logging
from app.telemetry import configure_tracing, tracer

log = logging.getLogger(__name__)

# Enough for a shopping conversation; past this the history is trimmed rather
# than sent, because every turn is re-read by the model and paid for again.
MAX_TURNS = 20
MAX_MESSAGE_CHARS = 2000

# A photograph from a phone, not a scan. Past this the model is paying to read
# detail no listing needs, and the request is slower for nobody's benefit.
MAX_PHOTO_BYTES = 6 * 1024 * 1024
PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}

# A voice note, not a podcast: a minute and a half of opus is a couple of
# hundred kilobytes, so anything approaching this is a recording nobody meant
# to send. The containers are the ones browsers actually record — Chrome gives
# webm, Safari mp4, Firefox ogg — and all four were accepted by the model
# before this was written, so nothing is transcoded on the way through.
MAX_VOICE_BYTES = 3 * 1024 * 1024
VOICE_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/aac",
    "audio/flac",
}
# A few sentences in Bangla. Bengali is three bytes a character in UTF-8, so
# this is characters rather than bytes on purpose.
MAX_NOTES_CHARS = 2000


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

    catalog = CatalogClient(config.catalog_url, config.request_timeout)
    app.state.config = config
    app.state.assistant = Assistant(
        config,
        catalog,
        CheckoutClient(config.checkout_url, config.request_timeout),
    )
    app.state.drafter = ListingDrafter(app.state.assistant.provider, catalog)
    # After the app exists, so the middleware wraps the routes below, and
    # before it serves anything.
    configure_tracing("assistant", app)
    log.info(
        "assistant ready",
        extra={"provider": config.provider, "models": ", ".join(config.models)},
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
        with tracer().start_as_current_span("assistant.turn") as span:
            span.set_attribute("poshra.turns_sent", len(conversation))
            answer = await assistant.reply(conversation, cookie=cookie or "")
            # On the span rather than only in the log line: "why did this one
            # take thirty seconds" is answered by the tool calls, and the tool
            # calls are only meaningful next to the spans they caused.
            span.set_attribute("poshra.tool_calls", answer["tool_calls"])
            span.set_attribute("poshra.products", len(answer["products"]))
            span.set_attribute("poshra.checkout_ready", answer["checkout_ready"])
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


@app.post("/draft-listing")
async def draft_listing(
    request: Request,
    notes: str = Form(default=""),
    craft: str = Form(default=""),
    district: str = Form(default=""),
    photo: UploadFile | None = File(default=None),
    voice: UploadFile | None = File(default=None),
    x_user_id: str | None = Header(default=None),
) -> JSONResponse:
    """A photograph and a few words in Bangla, returned as a listing to correct.

    Multipart rather than JSON: the photograph is the point, and base64 in a
    JSON body would make it a third larger for no gain.

    Nothing here writes. The draft is handed back to the form the artisan is
    already looking at, and she is the one who decides what the shop sees.
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Sign in to draft a listing.")

    photograph = await _read_photograph(photo)
    recording = await _read_recording(voice)
    if len(notes) > MAX_NOTES_CHARS:
        notes = notes[:MAX_NOTES_CHARS]

    drafter: ListingDrafter = request.app.state.drafter
    try:
        with tracer().start_as_current_span("assistant.draft_listing") as span:
            # What was sent decides what the call costs and how long it takes:
            # a photograph and a recording are most of both.
            span.set_attribute("poshra.had_photo", photograph is not None)
            span.set_attribute("poshra.had_voice", recording is not None)
            span.set_attribute("poshra.notes_chars", len(notes))
            drafted = await drafter.draft(
                notes=notes,
                photograph=photograph,
                recording=recording,
                craft_hint=craft.strip(),
                district=district.strip(),
            )
            span.set_attribute("poshra.confidence", drafted["confidence"])
            span.set_attribute("poshra.priced", bool(drafted["suggested_price_minor"]))
    except NothingToDraftFrom as error:
        raise HTTPException(
            status_code=400,
            detail="Add a photograph, say a few words, or describe the piece.",
        ) from error
    except CannotHearHer as error:
        # A deployment decision, not her mistake, so the message says what to
        # do rather than what went wrong.
        log.error("provider cannot hear", extra={"error": str(error)})
        raise HTTPException(
            status_code=503,
            detail="This assistant cannot listen to recordings. Type a few words instead.",
        ) from error
    except RateLimited as error:
        log.warning("model rate limited", extra={"error": str(error), "user_id": x_user_id})
        raise HTTPException(
            status_code=429,
            detail="Every model is busy right now. Try again in a minute.",
        ) from error
    except DraftFailed as error:
        log.error("draft was not usable", extra={"error": str(error), "user_id": x_user_id})
        raise HTTPException(
            status_code=503,
            detail="The draft came back unusable. Try again, or write it yourself.",
        ) from error
    except Exception as error:  # noqa: BLE001
        log.error("drafting failed", extra={"error": str(error), "user_id": x_user_id})
        raise HTTPException(status_code=503, detail="Drafting is unavailable right now.") from error

    log.info(
        "drafted a listing",
        extra={
            "user_id": x_user_id,
            "had_photo": photograph is not None,
            "had_voice": recording is not None,
            "notes_chars": len(notes),
            "confidence": drafted["confidence"],
            "craft": drafted["craft"],
            "priced": bool(drafted["suggested_price_minor"]),
        },
    )
    return JSONResponse(drafted)


async def _read_photograph(photo: UploadFile | None) -> Photograph | None:
    """Read the upload, refusing anything that is not a photograph of a size."""
    if photo is None or not photo.filename:
        return None

    media_type = (photo.content_type or "").split(";")[0].strip().lower()
    if media_type not in PHOTO_TYPES:
        raise HTTPException(
            status_code=415,
            detail="A photograph has to be a JPEG, PNG or WebP.",
        )

    # Read to the cap plus one byte: enough to know it is over without holding
    # a file of any size in memory to find out.
    data = await photo.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=413,
            detail="That photograph is too large — six megabytes is plenty.",
        )
    if not data:
        return None
    return Photograph(media_type=media_type, data=data)


async def _read_recording(voice: UploadFile | None) -> Recording | None:
    """Read the voice note, refusing anything that is not one."""
    if voice is None or not voice.filename:
        return None

    # Browsers label a recording with its codec — "audio/webm;codecs=opus" —
    # and the parameter is not part of the type the model is told about.
    media_type = (voice.content_type or "").split(";")[0].strip().lower()
    if media_type not in VOICE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="That recording is in a format the assistant cannot play.",
        )

    data = await voice.read(MAX_VOICE_BYTES + 1)
    if len(data) > MAX_VOICE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="That recording is too long — a minute or two is plenty.",
        )
    if not data:
        return None
    return Recording(media_type=media_type, data=data)
