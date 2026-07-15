import json
from pathlib import Path

import druks.redis
import httpx
import pytest
from conftest import configure_app_for_test, connect_harness, make_settings
from druks.accounts.models import Account
from druks.accounts.sessions import SESSION_COOKIE
from druks.harnesses import base as hbase
from druks.harnesses.models import HarnessLogin
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _clear_redis():
    druks.redis.get_client()._data.clear()
    yield


def _client(tmp_path: Path, **settings_overrides) -> TestClient:
    app = configure_app_for_test(
        settings=make_settings(tmp_path, **settings_overrides), authenticated=False
    )
    return TestClient(app)


def _grant(email: str = "me@example.com") -> dict:
    return {
        "access_token": "AT",
        "refresh_token": "RT",
        "expires_in": 28800,
        "scope": "user:profile",
        "account": {"email_address": email},
    }


def _mock_exchange(monkeypatch, grant: dict):
    async def fake_post(self, url, *, json=None, data=None, **_kwargs):
        return httpx.Response(200, text=_dumps(grant), request=httpx.Request("POST", url))

    monkeypatch.setattr(hbase.httpx.AsyncClient, "post", fake_post)


def _dumps(value: dict) -> str:
    return json.dumps(value)


def _login(client: TestClient, monkeypatch, *, email="me@example.com", headers=None) -> dict:
    start = client.post("/api/auth/harnesses/claude/login/start", headers=headers or {})
    assert start.status_code == 200
    _mock_exchange(monkeypatch, _grant(email))
    complete = client.post(
        "/api/auth/harnesses/claude/login/complete",
        json={"code": "thecode", "loginId": start.json()["loginId"]},
        headers=headers or {},
    )
    return complete


def test_protected_routes_401_without_a_session(tmp_path):
    with _client(tmp_path) as client:
        assert client.get("/api/auth/session").status_code == 401
        assert client.get("/api/settings/harnesses").status_code == 401
        # SSE authenticates from the cookie before any stream starts.
        assert client.get("/api/events/stream").status_code == 401
        # Health stays open.
        assert client.get("/health").status_code == 200


def test_login_flow_mints_session_and_account(tmp_path, monkeypatch, db_session):
    with _client(tmp_path) as client:
        start = client.post("/api/auth/harnesses/claude/login/start")
        assert start.json()["authorizeUrl"].startswith("https://claude.ai/oauth/authorize?")

        response = _login(client, monkeypatch)
        assert response.status_code == 200
        assert response.json()["email"] == "me@example.com"
        cookie = response.headers["set-cookie"]
        assert SESSION_COOKIE in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=Lax" in cookie
        assert "Path=/" in cookie

        session = client.get("/api/auth/session")
        assert session.status_code == 200
        assert session.json()["email"] == "me@example.com"

        # The session opens the protected surface, and the card shows the login.
        claude = {h["name"]: h for h in client.get("/api/settings/harnesses").json()}["claude"]
        assert claude["connected"] is True
        assert claude["account"] == "me@example.com"
        assert claude["isDefault"] is True


def test_login_start_unknown_harness_is_404(tmp_path):
    with _client(tmp_path) as client:
        assert client.post("/api/auth/harnesses/grok/login/start").status_code == 404


def test_touched_sessions_reissue_the_cookie(tmp_path, monkeypatch, db_session):
    with _client(tmp_path) as client:
        _login(client, monkeypatch)
        # Every authenticated response re-sets the sliding cookie — the
        # middleware writes it from the touched session, SSE included.
        response = client.get("/api/auth/session")
        assert SESSION_COOKIE in response.headers.get("set-cookie", "")
        assert "Max-Age" in response.headers["set-cookie"]


def test_login_complete_is_single_use(tmp_path, monkeypatch, db_session):
    with _client(tmp_path) as client:
        start = client.post("/api/auth/harnesses/claude/login/start")
        login_id = start.json()["loginId"]
        _mock_exchange(monkeypatch, _grant())
        first = client.post(
            "/api/auth/harnesses/claude/login/complete",
            json={"code": "thecode", "loginId": login_id},
        )
        assert first.status_code == 200
        second = client.post(
            "/api/auth/harnesses/claude/login/complete",
            json={"code": "thecode", "loginId": login_id},
        )
        assert second.status_code == 422


def test_logout_drops_the_session_and_clears_the_cookie(tmp_path, monkeypatch, db_session):
    with _client(tmp_path) as client:
        _login(client, monkeypatch)
        logout = client.post("/api/auth/logout")
        assert logout.status_code == 204
        assert "Max-Age=0" in logout.headers["set-cookie"]
        assert client.get("/api/auth/session").status_code == 401


def test_login_rotates_any_prior_session_token(tmp_path, monkeypatch, db_session):
    with _client(tmp_path) as client:
        first = _login(client, monkeypatch)
        first_token = client.cookies[SESSION_COOKIE]
        second = _login(client, monkeypatch)
        second_token = client.cookies[SESSION_COOKIE]
        assert first.status_code == second.status_code == 200
        assert first_token != second_token
        # The old token no longer resolves anywhere.
        client.cookies.set(SESSION_COOKIE, first_token)
        assert client.get("/api/auth/session").status_code == 401


def test_redis_eviction_signs_out_but_keeps_credentials(tmp_path, monkeypatch, db_session):
    with _client(tmp_path) as client:
        _login(client, monkeypatch)
        druks.redis.get_client()._data.clear()  # Redis loss
        assert client.get("/api/auth/session").status_code == 401
    # The durable credential is untouched — only the session died.
    assert HarnessLogin.get_default("claude") is not None


def test_proxy_mismatch_invalidates_the_session(tmp_path, monkeypatch, db_session):
    with _client(tmp_path) as client:
        _login(client, monkeypatch)
        assert client.get("/api/auth/session").status_code == 200
        # The trusted edge now asserts a different identity for this browser.
        mismatched = client.get(
            "/api/auth/session", headers={"X-ExeDev-Email": "other@example.com"}
        )
        assert mismatched.status_code == 401
        # The session is gone, not just masked while the header differs.
        assert client.get("/api/auth/session").status_code == 401


def test_proxy_identity_is_authoritative_for_the_account(tmp_path, monkeypatch, db_session):
    with _client(tmp_path) as client:
        response = _login(
            client,
            monkeypatch,
            email="personal@example.com",
            headers={"X-ExeDev-Email": " Ops@Corp.com "},
        )
        assert response.status_code == 200
        # Account = the trusted proxy identity, normalized; the provider email
        # stays on the login, visible as a mismatch that never blocks login.
        assert response.json()["email"] == "ops@corp.com"
        claude = {
            h["name"]: h
            for h in client.get(
                "/api/settings/harnesses", headers={"X-ExeDev-Email": "ops@corp.com"}
            ).json()
        }["claude"]
        assert claude["account"] == "ops@corp.com"
        assert claude["providerEmail"] == "personal@example.com"
        assert claude["isEmailMismatch"] is True


def test_session_keeps_its_account_across_reconnects(tmp_path, monkeypatch, db_session):
    with _client(tmp_path) as client:
        _login(client, monkeypatch, email="me@example.com")
        # Connect codex under the live session with a different provider email:
        # the session account wins; the seat records the provider identity.
        start = client.post("/api/auth/harnesses/codex/login/start")
        _mock_exchange_codex(monkeypatch, email="corp-seat@corp.com")
        complete = client.post(
            "/api/auth/harnesses/codex/login/complete",
            json={"code": "thecode", "loginId": start.json()["loginId"]},
        )
        assert complete.status_code == 200
        assert complete.json()["email"] == "me@example.com"
    account = Account.get_for_email("me@example.com")
    codex = HarnessLogin.get_for_account("codex", account.id)
    assert codex.provider_email == "corp-seat@corp.com"


def test_bound_reconnect_requires_its_session_at_complete(tmp_path, monkeypatch, db_session):
    with _client(tmp_path) as client:
        _login(client, monkeypatch, email="me@example.com")
        # An authenticated reconnect binds its flow to the session account…
        start = client.post("/api/auth/harnesses/codex/login/start")
        # …but the session dies before paste-back (eviction / logout).
        druks.redis.get_client()._data = {
            key: value
            for key, value in druks.redis.get_client()._data.items()
            if not key.startswith("druks:session:")
        }
        _mock_exchange_codex(monkeypatch, email="corp-seat@corp.com")
        response = client.post(
            "/api/auth/harnesses/codex/login/complete",
            json={"code": "thecode", "loginId": start.json()["loginId"]},
        )
        # The flow must never rebind the seat by email fallback.
        assert response.status_code == 422
        assert "different session" in response.json()["detail"]
    assert Account.get_for_email("corp-seat@corp.com") is None
    assert HarnessLogin.get_default("codex") is None


def test_two_accounts_may_connect_the_same_provider_login(tmp_path, monkeypatch, db_session):
    from druks.harnesses.claude import ClaudeHarness

    # druks does not police one-account-per-provider-login, deliberately: it
    # cannot identify the account behind one. Claude exposes no stable id, and
    # the email it does report is renameable upstream — so a constraint on it
    # would lapse silently the moment someone renames. Each connect is its own
    # authorization with its own refresh lineage, rotating under its own lock.
    connect_harness(
        ClaudeHarness,
        {"claudeAiOauth": {"accessToken": "x"}},
        provider_email="shared@corp.com",
    )
    with _client(tmp_path) as client:
        # Sign in as me@ via codex, then connect the same claude login.
        start = client.post("/api/auth/harnesses/codex/login/start")
        _mock_exchange_codex(monkeypatch, email="me@example.com")
        client.post(
            "/api/auth/harnesses/codex/login/complete",
            json={"code": "thecode", "loginId": start.json()["loginId"]},
        )
        assert _login(client, monkeypatch, email="shared@corp.com").status_code == 200

    claude = [login for login in HarnessLogin.list_all() if login.harness == "claude"]
    assert len(claude) == 2  # one row per account, same provider email
    assert len({login.account_id for login in claude}) == 2


def test_new_identity_cannot_acquire_legacy_seats(tmp_path, monkeypatch, db_session):
    from druks.harnesses.claude import ClaudeHarness

    # The PR1 migration shape: the dashboard account owns the legacy seat.
    legacy = connect_harness(
        ClaudeHarness, {"claudeAiOauth": {"accessToken": "x"}}, provider_email="op@example.com"
    )
    with _client(tmp_path) as client:
        response = _login(client, monkeypatch, email="newcomer@example.com")
        assert response.status_code == 200
    accounts = {account.email: account for account in _all_accounts()}
    assert set(accounts) == {"op@example.com", "newcomer@example.com"}
    # The newcomer got an empty account plus their own seat; the legacy seat
    # stays where the migration put it, still the default.
    assert HarnessLogin.reload(legacy.id).account_id == accounts["op@example.com"].id
    assert HarnessLogin.get_default("claude").id == legacy.id


def test_dashboard_identity_resolves_the_migrated_account(tmp_path, monkeypatch, db_session):
    from druks.harnesses.claude import ClaudeHarness

    legacy = connect_harness(
        ClaudeHarness, {"claudeAiOauth": {"accessToken": "x"}}, provider_email="op@example.com"
    )
    legacy_id = legacy.id
    with _client(tmp_path) as client:
        response = _login(client, monkeypatch, email="op@example.com")
        assert response.status_code == 200
    # Exact normalized-email match: one account, the legacy seat updated in
    # place. Read past this task's identity map — the request wrote in its own.
    assert len(_all_accounts()) == 1
    updated = HarnessLogin.reload(legacy_id)
    assert dict(updated.payload)["claudeAiOauth"]["accessToken"] == "AT"


def _all_accounts() -> list[Account]:
    from druks.database import db_session as registry
    from sqlalchemy import select

    return list(registry().scalars(select(Account)))


def _mock_exchange_codex(monkeypatch, *, email: str):
    import base64

    def _jwt(claims: dict) -> str:
        header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
        return f"{header}.{payload}.sig"

    access = _jwt(
        {
            "https://api.openai.com/auth": {"chatgpt_account_id": "acc-1"},
            "https://api.openai.com/profile": {"email": email},
            "exp": 4102444800,
        }
    )
    grant = {"access_token": access, "refresh_token": "RT", "id_token": "ID"}

    async def fake_post(self, url, *, json=None, data=None, **_kwargs):
        return httpx.Response(200, text=_dumps(grant), request=httpx.Request("POST", url))

    monkeypatch.setattr(hbase.httpx.AsyncClient, "post", fake_post)
