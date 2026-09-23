import pytest
from fastapi.testclient import TestClient

from app.assistant import Assistant
from app.catalog import CatalogClient
from app.config import Config
from app.main import MAX_MESSAGE_CHARS, app

CONFIG = Config(
    anthropic_api_key="unused",
    catalog_url="http://catalog",
    model="claude-opus-5",
    max_tokens=512,
    max_tool_calls=2,
    request_timeout=1.0,
)


class StubAssistant(Assistant):
    def __init__(self) -> None:
        super().__init__(CONFIG, CatalogClient(CONFIG.catalog_url, 1.0), client=object())
        self.seen: list[list[dict]] = []

    async def reply(self, messages):
        self.seen.append(messages)
        return {"reply": "Two pieces.", "products": [], "tool_calls": 1}


@pytest.fixture
def client(monkeypatch):
    # Startup reads real configuration and refuses to run without it, which is
    # the behaviour we want in production; here it just needs satisfying.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("CATALOG_URL", CONFIG.catalog_url)

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
