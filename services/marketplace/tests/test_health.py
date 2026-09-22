from unittest import mock

from django.db.utils import OperationalError


def test_healthz_returns_ok_without_touching_the_database(client):
    with mock.patch("config.health.connection") as db:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    db.cursor.assert_not_called()


def test_readyz_returns_ready_when_database_answers(client):
    with mock.patch("config.health.connection") as db:
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["checks"]["database"] == "ok"
    db.cursor.return_value.__enter__.return_value.execute.assert_called_once_with("SELECT 1")


def test_readyz_returns_503_when_database_is_down(client):
    with mock.patch("config.health.connection") as db:
        db.cursor.side_effect = OperationalError("connection refused")
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "checks": {"database": "fail"}}


def test_health_endpoints_reject_writes(client):
    assert client.post("/healthz").status_code == 405
