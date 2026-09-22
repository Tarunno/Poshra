import jwt
import pytest
from django.conf import settings
from django.utils import timezone

from accounts import services
from accounts.models import RefreshToken, Role, User
from accounts.tokens import decode_access_token

pytestmark = pytest.mark.django_db

LOGIN = "/auth/login"
REFRESH = "/auth/refresh"
LOGOUT = "/auth/logout"
REGISTER = "/auth/register"

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="artisan@poshra.test", password=PASSWORD, role=Role.ARTISAN
    )


def login(client, email="artisan@poshra.test", password=PASSWORD):
    return client.post(
        LOGIN, {"email": email, "password": password}, content_type="application/json"
    )


def csrf_headers(client):
    return {"HTTP_X_CSRF_TOKEN": client.cookies[settings.CSRF_COOKIE_NAME_AUTH].value}


# --- registration -----------------------------------------------------------


def test_register_creates_a_buyer_by_default(client):
    response = client.post(
        REGISTER,
        {"email": "Buyer@Poshra.test", "password": PASSWORD, "full_name": "Ayesha"},
        content_type="application/json",
    )
    assert response.status_code == 201
    assert response.json()["role"] == Role.BUYER
    # Emails are normalised, so "Buyer@" and "buyer@" are the same account.
    assert User.objects.get(email="buyer@poshra.test").full_name == "Ayesha"


def test_register_rejects_privilege_escalation(client):
    response = client.post(
        REGISTER,
        {"email": "sneaky@poshra.test", "password": PASSWORD, "role": "admin"},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert not User.objects.filter(email="sneaky@poshra.test").exists()


def test_register_rejects_duplicate_email(client, user):
    response = client.post(
        REGISTER,
        {"email": user.email, "password": PASSWORD},
        content_type="application/json",
    )
    assert response.status_code == 409


def test_password_is_never_stored_in_plaintext(user):
    user.refresh_from_db()
    assert PASSWORD not in user.password
    assert user.check_password(PASSWORD)


# --- login ------------------------------------------------------------------


def test_login_sets_httponly_cookies_and_returns_no_tokens(client, user):
    response = login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == user.email
    # Tokens must not be in the body: that is how they end up in JS and logs.
    assert "access" not in body and "token" not in body

    access = client.cookies[settings.ACCESS_COOKIE_NAME]
    refresh = client.cookies[settings.REFRESH_COOKIE_NAME]
    csrf = client.cookies[settings.CSRF_COOKIE_NAME_AUTH]
    assert access["httponly"] and refresh["httponly"]
    assert not csrf["httponly"]  # the page must read it to echo it back
    assert refresh["path"] == settings.REFRESH_COOKIE_PATH
    assert refresh["samesite"] == "Strict"


def test_access_token_claims(client, user):
    login(client)
    token = client.cookies[settings.ACCESS_COOKIE_NAME].value

    claims = decode_access_token(token)
    assert claims["sub"] == str(user.id)
    assert claims["role"] == Role.ARTISAN
    assert claims["iss"] == settings.JWT_ISSUER
    assert claims["aud"] == settings.JWT_AUDIENCE
    assert claims["exp"] - claims["iat"] == settings.JWT_ACCESS_TTL_SECONDS
    # The key id lets a verifier pick the right public key during rotation.
    assert jwt.get_unverified_header(token)["kid"] == settings.JWT_KEY_ID
    assert jwt.get_unverified_header(token)["alg"] == "RS256"


def test_login_with_wrong_password_is_rejected(client, user):
    assert login(client, password="wrong").status_code == 401
    assert settings.ACCESS_COOKIE_NAME not in client.cookies


def test_login_with_unknown_email_is_rejected(client):
    assert login(client, email="nobody@poshra.test").status_code == 401


def test_disabled_account_cannot_log_in(client, user):
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert login(client).status_code == 401


def test_refresh_token_is_stored_hashed(client, user):
    login(client)
    raw = client.cookies[settings.REFRESH_COOKIE_NAME].value
    stored = RefreshToken.objects.get(user=user)
    assert stored.token_hash != raw
    assert len(stored.token_hash) == 64  # sha256 hex


# --- refresh and rotation ---------------------------------------------------


def test_refresh_rotates_the_token(client, user):
    login(client)
    first = client.cookies[settings.REFRESH_COOKIE_NAME].value

    response = client.post(REFRESH, **csrf_headers(client))
    assert response.status_code == 200

    second = client.cookies[settings.REFRESH_COOKIE_NAME].value
    assert second != first
    assert RefreshToken.objects.filter(user=user).count() == 2
    # Both belong to the same login session.
    assert RefreshToken.objects.values_list("family", flat=True).distinct().count() == 1


def test_reusing_an_old_refresh_token_revokes_the_whole_family(client, user):
    login(client)
    stolen = client.cookies[settings.REFRESH_COOKIE_NAME].value
    client.post(REFRESH, **csrf_headers(client))  # legitimate rotation

    # An attacker replays the token they captured earlier.
    client.cookies[settings.REFRESH_COOKIE_NAME] = stolen
    response = client.post(REFRESH, **csrf_headers(client))

    assert response.status_code == 401
    assert "reuse" in response.json()["detail"].lower()
    # Everything from that login is now dead, including the legitimate token.
    assert not RefreshToken.objects.filter(user=user, revoked_at__isnull=True).exists()


def test_refresh_requires_the_csrf_header(client, user):
    login(client)
    assert client.post(REFRESH).status_code == 403


def test_refresh_rejects_a_mismatched_csrf_header(client, user):
    login(client)
    assert client.post(REFRESH, HTTP_X_CSRF_TOKEN="not-the-cookie").status_code == 403


def test_expired_refresh_token_is_rejected(client, user):
    login(client)
    RefreshToken.objects.filter(user=user).update(
        expires_at=timezone.now() - timezone.timedelta(seconds=1)
    )
    assert client.post(REFRESH, **csrf_headers(client)).status_code == 401


def test_refresh_without_a_token_is_rejected(client, user):
    login(client)
    del client.cookies[settings.REFRESH_COOKIE_NAME]
    assert client.post(REFRESH, **csrf_headers(client)).status_code == 401


# --- logout -----------------------------------------------------------------


def test_logout_revokes_the_session_and_clears_cookies(client, user):
    login(client)
    response = client.post(LOGOUT, **csrf_headers(client))

    assert response.status_code == 200
    assert not RefreshToken.objects.filter(user=user, revoked_at__isnull=True).exists()
    assert client.cookies[settings.ACCESS_COOKIE_NAME].value == ""

    # The old refresh token no longer works.
    assert client.post(REFRESH, HTTP_X_CSRF_TOKEN="x").status_code in (401, 403)


# --- keys -------------------------------------------------------------------


def test_jwks_exposes_only_public_key_material(client):
    body = client.get("/auth/jwks.json").json()
    key = body["keys"][0]
    assert key["kty"] == "RSA" and key["alg"] == "RS256"
    assert key["kid"] == settings.JWT_KEY_ID
    assert set(key) == {"kty", "use", "alg", "kid", "n", "e"}  # no private parts


def test_token_signed_with_another_key_is_rejected(client, user):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    forged = jwt.encode(
        {
            "sub": str(user.id),
            "role": Role.ADMIN,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "iat": 0,
            "exp": 9999999999,
        },
        attacker_key.decode(),
        algorithm="RS256",
    )
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(forged)


def test_service_layer_login_returns_usable_pair(user):
    pair = services.login(user.email, PASSWORD)
    assert decode_access_token(pair.access.value)["sub"] == str(user.id)
    assert pair.refresh.is_usable


# --- current user -----------------------------------------------------------


def test_me_returns_the_logged_in_user(client, user):
    login(client)
    body = client.get("/auth/me").json()
    assert body["email"] == user.email
    assert body["role"] == Role.ARTISAN


def test_me_without_a_session_is_401(client):
    assert client.get("/auth/me").status_code == 401


def test_me_prefers_the_gateway_identity_header(client, user):
    other = User.objects.create_user(email="buyer@poshra.test", password=PASSWORD)
    login(client)  # cookie belongs to `user`
    body = client.get("/auth/me", HTTP_X_USER_ID=str(other.id)).json()
    assert body["email"] == other.email


def test_auth_endpoints_are_throttled(client, settings, user):
    """The service rate-limits itself, even though the gateway also does."""
    from django.core.cache import cache

    cache.clear()
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {"auth": "3/min"},
    }
    from rest_framework.throttling import ScopedRateThrottle

    ScopedRateThrottle.THROTTLE_RATES = {"auth": "3/min"}
    try:
        codes = [login(client, password="wrong").status_code for _ in range(5)]
    finally:
        ScopedRateThrottle.THROTTLE_RATES = {"auth": None}
        cache.clear()

    assert codes[:3] == [401, 401, 401]
    assert 429 in codes[3:]
