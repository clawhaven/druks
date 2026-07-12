import base64
import json
from datetime import UTC, datetime, timedelta

import druks.redis
import httpx
import pytest
from druks.harnesses import base as hbase
from druks.harnesses.claude import ClaudeHarness
from druks.harnesses.codex import CodexHarness
from druks.harnesses.exceptions import LoginError
from druks.harnesses.models import HarnessLogin


@pytest.fixture(autouse=True)
def _clear_pending():
    # The suite shares one in-memory fake Redis; clear the login pending keys so
    # one test's stash never leaks into another.
    druks.redis.get_client()._data.clear()
    yield


def _jwt(claims: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.sig"


def _resp(status: int, body: object) -> httpx.Response:
    text = body if isinstance(body, str) else json.dumps(body)
    return httpx.Response(status, text=text, request=httpx.Request("POST", "https://x"))


def _mock_post(monkeypatch, response):
    calls = []

    async def fake_post(self, url, *, json=None, data=None, **_kwargs):
        calls.append({"url": url, "json": json, "data": data})
        return response

    monkeypatch.setattr(hbase.httpx.AsyncClient, "post", fake_post)
    return calls


async def _pending(harness: str) -> dict | None:
    raw = await druks.redis.get_client().get(f"druks:login:pending:{harness}")
    return json.loads(raw) if raw else None


async def test_claude_login_start_builds_url_and_stashes_pending(db_session):
    url = await ClaudeHarness.login_start()
    assert url.startswith("https://claude.ai/oauth/authorize?")
    assert "code=true" in url
    assert "code_challenge_method=S256" in url
    assert "client_id=9d1c250a-e61b-44d9-88ed-5944d1962f5e" in url

    pending = await _pending("claude")
    assert pending["state"] == pending["verifier"]  # claude echoes the verifier as state


async def test_claude_login_complete_stores_credential_and_account(monkeypatch, db_session):
    await ClaudeHarness.login_start()
    calls = _mock_post(
        monkeypatch,
        _resp(
            200,
            {
                "access_token": "AT",
                "refresh_token": "RT",
                "expires_in": 28800,
                "scope": "user:profile user:inference",
                "account": {"email_address": "me@example.com"},
            },
        ),
    )
    await ClaudeHarness.login_complete("thecode")

    login = HarnessLogin.get("claude")
    assert login is not None
    block = login.payload["claudeAiOauth"]
    assert block["accessToken"] == "AT"
    assert block["refreshToken"] == "RT"
    assert block["scopes"] == ["user:profile", "user:inference"]
    assert login.account == "me@example.com"
    # Claude exchanges JSON with the code + state echoed in the body.
    assert calls[0]["json"]["code"] == "thecode"
    assert "state" in calls[0]["json"]
    # Single-use: the pending state is gone.
    assert await _pending("claude") is None


async def test_codex_login_complete_is_form_encoded_and_reads_jwt(monkeypatch, db_session):
    await CodexHarness.login_start()
    pending = await _pending("codex")
    access = _jwt(
        {
            "https://api.openai.com/auth": {"chatgpt_account_id": "acc-9"},
            "https://api.openai.com/profile": {"email": "c@example.com"},
            "exp": int((datetime.now(UTC) + timedelta(days=10)).timestamp()),
        }
    )
    calls = _mock_post(
        monkeypatch, _resp(200, {"access_token": access, "refresh_token": "RT", "id_token": "ID"})
    )
    await CodexHarness.login_complete(
        f"http://localhost:1455/auth/callback?code=thecode&state={pending['state']}"
    )

    login = HarnessLogin.get("codex")
    assert login.payload["tokens"]["account_id"] == "acc-9"
    assert login.payload["tokens"]["id_token"] == "ID"
    assert login.account == "c@example.com"
    # Codex exchanges form-encoded, no state in the body.
    assert calls[0]["data"]["code"] == "thecode"
    assert "state" not in calls[0]["data"]


async def test_login_complete_unreadable_provider_json_raises_login_error(monkeypatch, db_session):
    await ClaudeHarness.login_start()
    _mock_post(monkeypatch, _resp(200, "not json"))

    with pytest.raises(LoginError) as error:
        await ClaudeHarness.login_complete("code")

    assert "unreadable response" in str(error.value)


async def test_login_complete_without_pending_raises(db_session):
    with pytest.raises(LoginError):
        await ClaudeHarness.login_complete("code")


async def test_login_complete_state_mismatch_raises(db_session):
    await ClaudeHarness.login_start()
    with pytest.raises(LoginError):
        await ClaudeHarness.login_complete("code#not-the-state")


async def test_login_complete_provider_error_clears_pending(monkeypatch, db_session):
    await ClaudeHarness.login_start()
    _mock_post(monkeypatch, _resp(400, "invalid_grant: code expired"))
    with pytest.raises(LoginError) as error:
        await ClaudeHarness.login_complete("code")
    assert "invalid_grant" in str(error.value)
    # Failure is single-use too — a retry must re-start.
    assert await _pending("claude") is None
    assert HarnessLogin.get("claude") is None


def test_disconnect_deletes_the_row(db_session):
    ClaudeHarness.store_credentials({"claudeAiOauth": {"accessToken": "x", "refreshToken": "r"}})
    assert HarnessLogin.get("claude") is not None
    ClaudeHarness.disconnect()
    assert HarnessLogin.get("claude") is None
