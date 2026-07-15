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


async def _pending(flow_id: str) -> dict | None:
    raw = await druks.redis.get_client().get(f"druks:login:pending:{flow_id}")
    return json.loads(raw) if raw else None


_CLAUDE_GRANT = {
    "access_token": "AT",
    "refresh_token": "RT",
    "expires_in": 28800,
    "scope": "user:profile user:inference",
    "account": {"email_address": "me@example.com"},
}


async def test_claude_login_start_builds_url_and_stashes_pending(db_session):
    url, flow_id = await ClaudeHarness.login_start()
    assert url.startswith("https://claude.ai/oauth/authorize?")
    assert "code=true" in url
    assert "code_challenge_method=S256" in url
    assert "client_id=9d1c250a-e61b-44d9-88ed-5944d1962f5e" in url

    pending = await _pending(flow_id)
    assert pending["state"] == pending["verifier"]  # claude echoes the verifier as state
    # An initial login binds to nothing until account resolution.
    assert pending["account_id"] is None
    assert pending["proxy_email"] is None


async def test_login_start_binds_flow_identities(db_session):
    _, flow_id = await ClaudeHarness.login_start(
        account_id="acct-1", proxy_email="ops@corp.com"
    )
    pending = await _pending(flow_id)
    assert pending["account_id"] == "acct-1"
    assert pending["proxy_email"] == "ops@corp.com"


async def test_claude_login_complete_returns_the_exchange(monkeypatch, db_session):
    _, flow_id = await ClaudeHarness.login_start(account_id="acct-1", proxy_email="p@corp.com")
    calls = _mock_post(monkeypatch, _resp(200, _CLAUDE_GRANT))
    completed = await ClaudeHarness.login_complete(flow_id=flow_id, pasted="thecode")

    block = completed.payload["claudeAiOauth"]
    assert block["accessToken"] == "AT"
    assert block["refreshToken"] == "RT"
    assert block["scopes"] == ["user:profile", "user:inference"]
    assert completed.provider_email == "me@example.com"
    assert completed.expires_at is not None
    # The identities the flow was started under ride along for resolution.
    assert completed.account_id == "acct-1"
    assert completed.proxy_email == "p@corp.com"
    # Claude exchanges JSON with the code + state echoed in the body.
    assert calls[0]["json"]["code"] == "thecode"
    assert "state" in calls[0]["json"]
    # Single-use: the pending state is gone.
    assert await _pending(flow_id) is None


async def test_concurrent_login_flows_do_not_clobber_each_other(monkeypatch, db_session):
    # Two people connect the same harness at once: distinct flow ids, both
    # pendings live, and completing one leaves the other completable.
    _, first_flow = await ClaudeHarness.login_start()
    _, second_flow = await ClaudeHarness.login_start()
    assert first_flow != second_flow

    _mock_post(monkeypatch, _resp(200, _CLAUDE_GRANT))
    first = await ClaudeHarness.login_complete(flow_id=first_flow, pasted="code-1")
    assert await _pending(second_flow) is not None

    second_grant = dict(_CLAUDE_GRANT, account={"email_address": "other@example.com"})
    _mock_post(monkeypatch, _resp(200, second_grant))
    second = await ClaudeHarness.login_complete(flow_id=second_flow, pasted="code-2")

    assert first.provider_email == "me@example.com"
    assert second.provider_email == "other@example.com"


async def test_login_complete_without_provider_email_raises(monkeypatch, db_session):
    _, flow_id = await ClaudeHarness.login_start()
    grant = dict(_CLAUDE_GRANT, account={})
    _mock_post(monkeypatch, _resp(200, grant))
    with pytest.raises(LoginError, match="no account email"):
        await ClaudeHarness.login_complete(flow_id=flow_id, pasted="thecode")


async def test_codex_login_complete_is_form_encoded_and_reads_jwt(monkeypatch, db_session):
    _, flow_id = await CodexHarness.login_start()
    pending = await _pending(flow_id)
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
    completed = await CodexHarness.login_complete(
        flow_id=flow_id,
        pasted=f"http://localhost:1455/auth/callback?code=thecode&state={pending['state']}",
    )

    assert completed.payload["tokens"]["account_id"] == "acc-9"
    assert completed.payload["tokens"]["id_token"] == "ID"
    assert completed.provider_email == "c@example.com"
    # Codex exchanges form-encoded, no state in the body.
    assert calls[0]["data"]["code"] == "thecode"
    assert "state" not in calls[0]["data"]


async def test_login_complete_unreadable_provider_json_raises_login_error(monkeypatch, db_session):
    _, flow_id = await ClaudeHarness.login_start()
    _mock_post(monkeypatch, _resp(200, "not json"))

    with pytest.raises(LoginError) as error:
        await ClaudeHarness.login_complete(flow_id=flow_id, pasted="code")

    assert "unreadable response" in str(error.value)


async def test_login_complete_without_pending_raises(db_session):
    with pytest.raises(LoginError):
        await ClaudeHarness.login_complete(flow_id="not-a-flow", pasted="code")


async def test_login_complete_state_mismatch_raises(db_session):
    _, flow_id = await ClaudeHarness.login_start()
    with pytest.raises(LoginError):
        await ClaudeHarness.login_complete(flow_id=flow_id, pasted="code#not-the-state")


async def test_login_complete_provider_error_clears_pending(monkeypatch, db_session):
    _, flow_id = await ClaudeHarness.login_start()
    _mock_post(monkeypatch, _resp(400, "invalid_grant: code expired"))
    with pytest.raises(LoginError) as error:
        await ClaudeHarness.login_complete(flow_id=flow_id, pasted="code")
    assert "invalid_grant" in str(error.value)
    # Failure is single-use too — a retry must re-start.
    assert await _pending(flow_id) is None
