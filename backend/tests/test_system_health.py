from pathlib import Path

import pytest
from conftest import configure_app_for_test, make_settings
from fastapi.testclient import TestClient

MODULE = "druks.api.health_status"


@pytest.fixture(autouse=True)
def _no_redis_freshness(monkeypatch):
    """Webhook freshness lives in Redis; tests have none running."""

    async def none(provider):
        return None

    monkeypatch.setattr(f"{MODULE}.last_delivery_at", none)


def _client(tmp_path: Path) -> TestClient:
    return TestClient(configure_app_for_test(settings=make_settings(tmp_path)))


def test_system_health_returns_health_block_only(tmp_path: Path):
    with _client(tmp_path) as client:
        r = client.get("/api/system/health")
    assert r.status_code == 200
    body = r.json()
    # The health fields the strip renders are present...
    assert body["web"] == "ok"
    assert "webhookFreshness" in body
    # ...and none of the research dashboard's heavier lists are.
    assert "signalsInbox" not in body
    assert "needsYou" not in body
    assert "inFlight" not in body
