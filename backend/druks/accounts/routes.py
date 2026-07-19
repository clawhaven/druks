from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response

from druks.accounts import sessions
from druks.accounts.constants import PAT_NAME_LENGTH
from druks.accounts.dependencies import (
    current_account,
    current_session_account,
    resolve_session_account,
)
from druks.accounts.models import Account, PersonalAccessToken
from druks.accounts.schemas import AccountResponse, PatResponse
from druks.harnesses.base import Harness
from druks.harnesses.exceptions import LoginError
from druks.harnesses.models import HarnessConnection
from druks.harnesses.registry import get_harness
from druks.user_settings.models import HarnessSettings, UserSettings

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _resolve_harness(name: str) -> type[Harness]:
    harness = get_harness(name)
    if harness:
        return harness
    raise HTTPException(status_code=404, detail=f"Unknown harness: {name!r}")


def _set_session_cookie(request: Request, response: Response, token: str) -> None:
    # The shipped edge terminates TLS and proxies loopback HTTP.
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    response.set_cookie(
        sessions.SESSION_COOKIE,
        token,
        max_age=sessions.SESSION_TTL_SECONDS if token else 0,
        httponly=True,
        samesite="lax",
        secure=scheme == "https",
    )


@router.get("/session", response_model=AccountResponse, response_model_by_alias=True)
async def get_session(
    request: Request, response: Response, account: Account = Depends(current_account)
) -> Account:
    # Slide the cookie with the Redis TTL; a Bearer request carries none.
    token = request.cookies.get(sessions.SESSION_COOKIE)
    if token:
        _set_session_cookie(request, response, token)
    return account


@router.post("/harnesses/{name}/login/start")
async def start_login(name: str, request: Request) -> dict[str, str]:
    harness = _resolve_harness(name)
    account = await resolve_session_account(request)
    url, login_id = await harness.login_start(account_id=account.id if account else None)
    return {"authorizeUrl": url, "loginId": login_id}


@router.post(
    "/harnesses/{name}/login/complete",
    response_model=AccountResponse,
    response_model_by_alias=True,
)
async def complete_login(
    name: str,
    request: Request,
    response: Response,
    code: str = Body(..., embed=True),
    login_id: str = Body(..., embed=True, alias="loginId"),
) -> Account:
    harness = _resolve_harness(name)
    session_account = await resolve_session_account(request)
    try:
        completed = await harness.login_complete(flow_id=login_id, pasted=code)
    except LoginError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if completed.account_id and (not session_account or completed.account_id != session_account.id):
        # A bound reconnect must never rebind the login by email fallback.
        raise HTTPException(
            status_code=422,
            detail="This sign-in was started under a different session — start it again.",
        )
    account = session_account or Account.get_or_create(completed.provider_email)
    # Runs with no actor execute as the fallback account; claim the slot when
    # none is set yet.
    settings = UserSettings.get()
    if not settings.fallback_account_id:
        settings.set_fallback_account(account.id)
    connection = HarnessConnection.connect(
        harness=harness.name,
        account=account,
        payload=completed.payload,
        expires_at=completed.expires_at,
        provider_email=completed.provider_email,
    )
    # Fresh picker right after login; failures are tagged inside, never raised.
    await HarnessSettings.require(harness.name).refresh_models(connection)
    old_token = request.cookies.get(sessions.SESSION_COOKIE)
    if old_token:
        await sessions.drop_session(old_token)  # login rotates the token
    _set_session_cookie(request, response, await sessions.mint_session(account.id))
    return account


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response) -> None:
    token = request.cookies.get(sessions.SESSION_COOKIE)
    if token:
        await sessions.drop_session(token)
    _set_session_cookie(request, response, "")


@router.get("/personal-tokens", response_model=list[PatResponse], response_model_by_alias=True)
async def list_pats(
    account: Account = Depends(current_session_account),
) -> list[PersonalAccessToken]:
    return PersonalAccessToken.list_for_account(account.id)


@router.post("/personal-tokens")
async def create_pat(
    account: Account = Depends(current_session_account),
    name: str = Body(..., embed=True),
) -> dict[str, str]:
    name = name.strip()
    if name and len(name) <= PAT_NAME_LENGTH:
        # The plaintext, handed back exactly once — only its hash is stored,
        # and the new row surfaces through the list.
        _, token = PersonalAccessToken.create(account_id=account.id, name=name)
        return {"token": token}
    raise HTTPException(
        status_code=422,
        detail=f"A token needs a name of at most {PAT_NAME_LENGTH} characters.",
    )


@router.delete(
    "/personal-tokens/{pat_id}", response_model=PatResponse, response_model_by_alias=True
)
async def revoke_pat(
    pat_id: str, account: Account = Depends(current_session_account)
) -> PersonalAccessToken:
    pat = PersonalAccessToken.get(pat_id)
    if pat and pat.account_id == account.id:
        pat.revoke()
        return pat
    # One shape for missing and foreign — existence stays account-scoped.
    raise HTTPException(status_code=404, detail="No such token.")
