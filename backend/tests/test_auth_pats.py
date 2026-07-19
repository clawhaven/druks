import hashlib
import secrets
from datetime import timedelta
from pathlib import Path

import druks.redis
import pytest
from conftest import configure_app_for_test, make_settings
from druks.accounts.constants import PAT_TOKEN_TAG, SESSION_PREFIX
from druks.accounts.exceptions import InvalidPatError
from druks.accounts.models import Account, PersonalAccessToken
from druks.accounts.sessions import SESSION_COOKIE
from druks.database import db_session as session_registry
from druks.models import Base
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _clear_redis():
    druks.redis.get_client()._data.clear()
    yield


def _client(tmp_path: Path) -> TestClient:
    app = configure_app_for_test(settings=make_settings(tmp_path), authenticated=False)
    return TestClient(app)


def _sign_in(client: TestClient, username: str = "op@example.com") -> Account:
    account = Account.get_or_create(username)
    token = f"session-{username}"
    druks.redis.get_client()._data[f"{SESSION_PREFIX}{token}"] = account.id.encode()
    client.cookies.set(SESSION_COOKIE, token)
    return account


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _mint(username: str = "agent@example.com") -> tuple[PersonalAccessToken, str]:
    account = Account.get_or_create(username)
    return PersonalAccessToken.create(account_id=account.id, name="agent")


def test_the_minted_token_shape_and_hash_are_pinned(db_session):
    pat, token = _mint()
    prefix, _, secret = token.removeprefix(f"{PAT_TOKEN_TAG}_").partition("_")
    assert token.startswith(f"{PAT_TOKEN_TAG}_")
    assert len(prefix) == 12
    assert len(secret) == 43
    assert pat.token_prefix == prefix
    # The stored hash is SHA-256 of the full serialized token: exactly 32 bytes.
    assert len(pat.token_hash) == 32
    assert pat.token_hash == hashlib.sha256(token.encode()).digest()
    assert pat.expires_at == pat.created_at + timedelta(days=365)
    assert not pat.last_used_at
    assert pat.is_active


def test_a_prefix_collision_regenerates(db_session, monkeypatch):
    first, _ = _mint()
    replay = iter(first.token_prefix)
    random_choice = secrets.choice

    def collide_once(alphabet):
        # Feed the taken prefix back once, then return to real randomness.
        try:
            return next(replay)
        except StopIteration:
            return random_choice(alphabet)

    monkeypatch.setattr(secrets, "choice", collide_once)
    second, _ = PersonalAccessToken.create(account_id=first.account_id, name="two")
    assert second.token_prefix != first.token_prefix


def test_authenticate_rejects_everything_but_the_live_token(db_session):
    pat, token = _mint()
    assert PersonalAccessToken.authenticate(token).id == pat.id
    with pytest.raises(InvalidPatError):
        PersonalAccessToken.authenticate("not-even-shaped-right")
    with pytest.raises(InvalidPatError):
        PersonalAccessToken.authenticate(f"{PAT_TOKEN_TAG}_{pat.token_prefix}_wrongsecret")

    pat.expires_at = Base.utc_now() - timedelta(days=1)
    with pytest.raises(InvalidPatError, match=f"{pat.token_prefix} has expired"):
        PersonalAccessToken.authenticate(token)

    pat.expires_at = Base.utc_now() + timedelta(days=1)
    pat.revoke()
    with pytest.raises(InvalidPatError, match=f"{pat.token_prefix} was revoked"):
        PersonalAccessToken.authenticate(token)


def test_last_used_advances_at_most_hourly(db_session):
    pat, token = _mint()
    PersonalAccessToken.authenticate(token)
    first_use = pat.last_used_at
    assert first_use
    PersonalAccessToken.authenticate(token)
    assert pat.last_used_at == first_use
    pat.last_used_at = first_use - timedelta(hours=2)
    PersonalAccessToken.authenticate(token)
    assert pat.last_used_at > first_use - timedelta(hours=2)


def test_a_bearer_pat_authenticates_gated_routes(tmp_path, db_session):
    with _client(tmp_path) as client:
        _, token = _mint()
        response = client.get("/api/auth/session", headers=_bearer(token))
        assert response.status_code == 200
        assert response.json()["username"] == "agent@example.com"
        # No cookie to slide on a Bearer request.
        assert "set-cookie" not in response.headers
        assert client.get("/api/settings", headers=_bearer(token)).status_code == 200


def test_an_authorization_header_never_falls_back_to_the_cookie(tmp_path, db_session):
    with _client(tmp_path) as client:
        _sign_in(client)
        assert client.get("/api/auth/session").status_code == 200
        response = client.get(
            "/api/auth/session", headers=_bearer(f"{PAT_TOKEN_TAG}_unknownpref1_nosecret")
        )
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == 'Bearer realm="druks", error="invalid_token"'


@pytest.mark.parametrize(
    "header", ["", "Token abc", "Bearer", "Bearer ", "Bearer a b", "bearer lowercased"]
)
def test_a_malformed_authorization_header_is_challenged(tmp_path, db_session, header):
    with _client(tmp_path) as client:
        response = client.get("/api/auth/session", headers={"Authorization": header})
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == 'Bearer realm="druks"'


def test_an_empty_authorization_header_never_slides_to_the_cookie(tmp_path, db_session):
    with _client(tmp_path) as client:
        _sign_in(client)
        response = client.get("/api/auth/session", headers={"Authorization": ""})
        assert response.status_code == 401


def test_a_dead_token_401s_with_its_prefix_only(tmp_path, db_session):
    with _client(tmp_path) as client:
        pat, token = _mint()
        pat.revoke()
        response = client.get("/api/auth/session", headers=_bearer(token))
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == 'Bearer realm="druks", error="invalid_token"'
        assert pat.token_prefix in response.json()["detail"]
        _, _, secret = token.removeprefix(f"{PAT_TOKEN_TAG}_").partition("_")
        assert secret not in response.text


def test_a_pat_cannot_manage_pats(tmp_path, db_session):
    with _client(tmp_path) as client:
        pat, token = _mint()
        assert client.get("/api/auth/personal-tokens", headers=_bearer(token)).status_code == 401
        create = client.post(
            "/api/auth/personal-tokens", json={"name": "x"}, headers=_bearer(token)
        )
        assert create.status_code == 401
        revoke = client.delete(f"/api/auth/personal-tokens/{pat.id}", headers=_bearer(token))
        assert revoke.status_code == 401


def test_the_session_manages_the_token_lifecycle(tmp_path, db_session):
    with _client(tmp_path) as client:
        _sign_in(client)
        created = client.post("/api/auth/personal-tokens", json={"name": "ci bot"})
        assert created.status_code == 200
        # Create answers only the plaintext, exactly once; the row surfaces
        # through the list.
        assert list(created.json()) == ["token"]
        token = created.json()["token"]
        assert token.startswith(f"{PAT_TOKEN_TAG}_")

        listed = client.get("/api/auth/personal-tokens").json()
        assert [item["name"] for item in listed] == ["ci bot"]
        assert token.split("_")[2] == listed[0]["prefix"]
        assert "token" not in listed[0]

        row_id = listed[0]["id"]
        revoked = client.delete(f"/api/auth/personal-tokens/{row_id}").json()
        assert revoked["isRevoked"] is True
        assert revoked["isActive"] is False
        # A repeat revoke answers the same state, same instant.
        again = client.delete(f"/api/auth/personal-tokens/{row_id}").json()
        assert again["revokedAt"] == revoked["revokedAt"]


def test_the_list_is_scoped_to_the_signed_in_account(tmp_path, db_session):
    with _client(tmp_path) as client:
        _mint("other@example.com")
        _sign_in(client)
        assert client.get("/api/auth/personal-tokens").json() == []


def test_revoking_anothers_token_is_a_404(tmp_path, db_session):
    with _client(tmp_path) as client:
        pat, _ = _mint("other@example.com")
        _sign_in(client)
        assert client.delete(f"/api/auth/personal-tokens/{pat.id}").status_code == 404
        session_registry().expire_all()
        assert not pat.revoked_at


def test_a_token_needs_a_name_that_fits(tmp_path, db_session):
    with _client(tmp_path) as client:
        _sign_in(client)
        assert client.post("/api/auth/personal-tokens", json={"name": "   "}).status_code == 422
        assert client.post("/api/auth/personal-tokens", json={"name": "x" * 81}).status_code == 422
