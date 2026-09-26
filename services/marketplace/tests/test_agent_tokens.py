"""Credentials a shopper hands to an AI agent.

The three things worth holding to: the token is shown once and never stored,
the gateway can verify it without asking anyone, and the shopper can take it
back.
"""

import jwt
import pytest
from django.conf import settings
from django.utils import timezone

from accounts.models import AgentToken, Role, User
from accounts.tokens import AGENT_TOKEN_TTL_DAYS

pytestmark = pytest.mark.django_db

TOKENS = "/agent-tokens"
INTROSPECT = "/agent-tokens/introspect"


@pytest.fixture
def shopper(db):
    return User.objects.create_user(
        email="shopper@poshra.test", password="correct-horse-battery-staple", role=Role.BUYER
    )


def as_user(client, user):
    """The gateway's header, which is the only identity a service trusts."""
    return {"HTTP_X_USER_ID": str(user.id), "HTTP_X_USER_ROLE": user.role}


def mint(client, user, label="Claude on my laptop"):
    return client.post(
        TOKENS, {"label": label}, content_type="application/json", **as_user(client, user)
    )


def test_anonymous_cannot_mint(client):
    assert client.post(TOKENS, {"label": "x"}, content_type="application/json").status_code == 401


def test_minting_returns_a_token_the_gateway_can_verify(client, shopper):
    response = mint(client, shopper)
    assert response.status_code == 201

    claims = jwt.decode(
        response.json()["token"],
        settings.JWT_PUBLIC_KEY,
        algorithms=["RS256"],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
    )
    # Same issuer, audience and key as a browser's token, so the gateway needs
    # no special case for agents.
    assert claims["sub"] == str(shopper.id)
    assert claims["role"] == Role.BUYER
    # What sets it apart: an agent, and a row that can be revoked.
    assert claims["scope"] == "agent"
    assert claims["jti"] == response.json()["id"]


def test_the_token_is_shown_once_and_never_stored(client, shopper):
    value = mint(client, shopper).json()["token"]

    listed = client.get(TOKENS, **as_user(client, shopper)).json()["results"]
    assert len(listed) == 1
    assert "token" not in listed[0]
    # Nothing in the row would let anyone reconstruct it.
    assert value not in str(listed[0])


def test_it_lives_long_enough_to_be_useful(client, shopper):
    record = AgentToken.objects.get(pk=mint(client, shopper).json()["id"])
    days = (record.expires_at - timezone.now()).days
    assert days >= AGENT_TOKEN_TTL_DAYS - 1


def test_a_shopper_sees_only_their_own(client, shopper):
    other = User.objects.create_user(email="other@poshra.test", password="x" * 14)
    mint(client, other, label="not yours")
    mint(client, shopper, label="mine")

    listed = client.get(TOKENS, **as_user(client, shopper)).json()["results"]
    assert [row["label"] for row in listed] == ["mine"]


def test_revoking_keeps_the_row_so_it_can_be_seen(client, shopper):
    token_id = mint(client, shopper).json()["id"]

    revoked = client.delete(f"{TOKENS}/{token_id}", **as_user(client, shopper))
    assert revoked.status_code == 200
    assert revoked.json()["active"] is False
    assert revoked.json()["revoked_at"] is not None
    assert AgentToken.objects.filter(pk=token_id).exists()


def test_cannot_revoke_somebody_elses(client, shopper):
    other = User.objects.create_user(email="other@poshra.test", password="x" * 14)
    token_id = mint(client, other).json()["id"]

    response = client.delete(f"{TOKENS}/{token_id}", **as_user(client, shopper))
    assert response.status_code == 404
    assert AgentToken.objects.get(pk=token_id).revoked_at is None


def introspect(client, token_id):
    return client.post(INTROSPECT, {"token_id": token_id}, content_type="application/json")


def test_introspection_is_how_revocation_takes_effect(client, shopper):
    """The gateway verifies a signature; only this row knows it was withdrawn."""
    token_id = mint(client, shopper).json()["id"]
    assert introspect(client, token_id).json() == {"active": True, "user_id": str(shopper.id)}

    client.delete(f"{TOKENS}/{token_id}", **as_user(client, shopper))
    assert introspect(client, token_id).json() == {"active": False}


def test_introspection_records_that_the_token_was_used(client, shopper):
    token_id = mint(client, shopper).json()["id"]
    assert AgentToken.objects.get(pk=token_id).last_used_at is None

    introspect(client, token_id)
    assert AgentToken.objects.get(pk=token_id).last_used_at is not None


def test_introspection_survives_rubbish(client):
    """An unknown or malformed id is a plain no, not a stack trace."""
    assert introspect(client, "not-a-uuid").json() == {"active": False}
    assert introspect(client, "").json() == {"active": False}
    assert introspect(client, "0192f2c0-0000-7000-8000-000000000001").json() == {"active": False}


def test_an_expired_token_is_not_active(client, shopper):
    token_id = mint(client, shopper).json()["id"]
    AgentToken.objects.filter(pk=token_id).update(
        expires_at=timezone.now() - timezone.timedelta(minutes=1)
    )
    assert introspect(client, token_id).json() == {"active": False}
