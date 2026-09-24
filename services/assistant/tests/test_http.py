import pytest
from fastapi.testclient import TestClient

from app.assistant import Assistant
from app.catalog import CatalogClient
from app.config import Config
from app.main import MAX_MESSAGE_CHARS, app

CONFIG = Config(
    provider="gemini",
    api_key="unused",
    models=("test-model",),
    catalog_url="http://catalog",
    checkout_url="http://checkout",
    max_tokens=512,
    max_tool_calls=2,
    request_timeout=1.0,
    llm_timeout=5.0,
)


class StubAssistant(Assistant):
    def __init__(self) -> None:
        super().__init__(CONFIG, CatalogClient(CONFIG.catalog_url, 1.0), provider=object())
        self.seen: list[list[dict]] = []

    async def reply(self, messages, cookie: str = ""):
        self.seen.append(messages)
        return {
            "reply": "Two pieces.",
            "products": [],
            "tool_calls": 1,
            "checkout_ready": False,
        }


@pytest.fixture
def client(monkeypatch):
    # Startup reads real configuration and refuses to run without it, which is
    # the behaviour we want in production; here it just needs satisfying.
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("CATALOG_URL", CONFIG.catalog_url)
    monkeypatch.setenv("CHECKOUT_URL", CONFIG.checkout_url)

    stub = StubAssistant()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        # Replace the real assistant that startup built, after it has run.
        app.state.assistant = stub
        yield test_client, stub


def test_liveness_never_touches_a_dependency(client):
    test_client, _ = client
    assert test_client.get("/healthz").json() == {"status": "ok"}


def test_asking_without_a_session_is_refused(client):
    test_client, _ = client
    response = test_client.post("/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    # Every answer costs money, so the assistant is not open to the world.
    assert response.status_code == 401


def test_a_signed_in_shopper_gets_an_answer(client):
    test_client, stub = client
    response = test_client.post(
        "/chat",
        json={"messages": [{"role": "user", "content": "show me a kantha"}]},
        headers={"X-User-Id": "user-1"},
    )
    assert response.status_code == 200
    assert response.json()["reply"] == "Two pieces."
    assert stub.seen[-1][-1]["content"] == "show me a kantha"


def test_the_last_message_must_be_the_shoppers(client):
    test_client, _ = client
    response = test_client.post(
        "/chat",
        json={"messages": [{"role": "assistant", "content": "hello"}]},
        headers={"X-User-Id": "user-1"},
    )
    assert response.status_code == 400


def test_an_oversized_message_is_rejected_before_it_reaches_the_model(client):
    test_client, stub = client
    response = test_client.post(
        "/chat",
        json={"messages": [{"role": "user", "content": "x" * (MAX_MESSAGE_CHARS + 1)}]},
        headers={"X-User-Id": "user-1"},
    )
    # Tokens are paid for by the character, so the ceiling is enforced here
    # rather than discovered on the bill.
    assert response.status_code == 422
    assert stub.seen == []


def test_an_empty_conversation_is_rejected(client):
    test_client, _ = client
    response = test_client.post("/chat", json={"messages": []}, headers={"X-User-Id": "user-1"})
    assert response.status_code == 422


def test_being_out_of_quota_says_wait_rather_than_broken(client, monkeypatch):
    from app.llm.gemini import RateLimited

    test_client, stub = client

    async def rate_limited(messages, cookie: str = ""):
        raise RateLimited("the model answered 429 4 times")

    monkeypatch.setattr(stub, "reply", rate_limited)
    response = test_client.post(
        "/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers={"X-User-Id": "user-1"},
    )

    # 429, not 503: the service is fine, the quota is not, and "try again in a
    # minute" is a different instruction from "it is down".
    assert response.status_code == 429
    assert "busy" in response.json()["detail"]


class StubDrafter:
    """Stands in for the model; records what the endpoint handed it."""

    def __init__(self) -> None:
        self.seen: dict | None = None

    async def draft(self, *, notes, photograph, recording=None, craft_hint="", district=""):
        self.seen = {
            "notes": notes,
            "photograph": photograph,
            "recording": recording,
            "craft_hint": craft_hint,
            "district": district,
        }
        return {
            "title": "Jute floor mat, indigo stripe",
            "description": "Handwoven in Faridpur.",
            "materials": "Jute",
            "dimensions": "",
            "craft": "jute-craft",
            "suggested_price_minor": 420000,
            "price_reasoning": "Close to a mat already listed.",
            "heard": "",
            "confidence": "high",
        }


@pytest.fixture
def drafting(client):
    test_client, _ = client
    stub = StubDrafter()
    app.state.drafter = stub
    return test_client, stub


def test_drafting_without_a_session_is_refused(drafting):
    test_client, _ = drafting
    response = test_client.post("/draft-listing", data={"notes": "পাটের পাটি"})
    # Drafting costs a model call, same as asking does.
    assert response.status_code == 401


def test_a_photograph_and_a_few_words_come_back_as_a_listing(drafting):
    test_client, stub = drafting
    response = test_client.post(
        "/draft-listing",
        data={"notes": "পাটের পাটি, ফরিদপুরে বোনা", "craft": "jute-craft"},
        files={"photo": ("mat.jpg", b"\xff\xd8\xff\xe0 pretend jpeg", "image/jpeg")},
        headers={"X-User-Id": "artisan-1"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Jute floor mat, indigo stripe"
    assert stub.seen["photograph"].media_type == "image/jpeg"
    assert stub.seen["craft_hint"] == "jute-craft"


def test_a_file_that_is_not_a_photograph_is_refused(drafting):
    test_client, _ = drafting
    response = test_client.post(
        "/draft-listing",
        data={"notes": "hello"},
        files={"photo": ("notes.pdf", b"%PDF-1.4", "application/pdf")},
        headers={"X-User-Id": "artisan-1"},
    )
    # The model would be paid to look at it either way.
    assert response.status_code == 415


def test_a_photograph_too_large_to_be_worth_reading_is_refused(drafting):
    from app.main import MAX_PHOTO_BYTES

    test_client, _ = drafting
    response = test_client.post(
        "/draft-listing",
        files={"photo": ("huge.png", b"x" * (MAX_PHOTO_BYTES + 10), "image/png")},
        headers={"X-User-Id": "artisan-1"},
    )
    assert response.status_code == 413


def test_nothing_to_draft_from_says_so(drafting):
    test_client, stub = drafting

    async def refuse(**kwargs):
        from app.listing import NothingToDraftFrom

        raise NothingToDraftFrom("nothing")

    stub.draft = refuse
    response = test_client.post(
        "/draft-listing", data={"notes": ""}, headers={"X-User-Id": "artisan-1"}
    )
    assert response.status_code == 400
    assert "photograph" in response.json()["detail"]


def test_a_voice_note_reaches_the_drafter(drafting):
    test_client, stub = drafting
    response = test_client.post(
        "/draft-listing",
        # What Chrome's MediaRecorder actually produces, codec parameter and
        # all — the parameter is not part of the type the model is told about.
        files={"voice": ("note.webm", b"\x1aE\xdf\xa3 pretend opus", "audio/webm;codecs=opus")},
        headers={"X-User-Id": "artisan-1"},
    )

    assert response.status_code == 200
    assert stub.seen["recording"].media_type == "audio/webm"


def test_a_recording_in_a_format_nothing_can_play_is_refused(drafting):
    test_client, _ = drafting
    response = test_client.post(
        "/draft-listing",
        files={"voice": ("note.amr", b"#!AMR", "audio/amr")},
        headers={"X-User-Id": "artisan-1"},
    )
    assert response.status_code == 415
