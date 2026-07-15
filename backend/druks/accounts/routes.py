from fastapi import APIRouter, Body, Depends, HTTPException, Request

from druks.accounts import sessions
from druks.accounts.dependencies import current_account, proxy_identity, resolve_session_account
from druks.accounts.models import Account
from druks.accounts.schemas import AccountResponse
from druks.harnesses.base import Harness
from druks.harnesses.exceptions import LoginError
from druks.harnesses.models import HarnessLogin
from druks.harnesses.registry import get_harnesses

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _resolve_harness(name: str) -> type[Harness]:
    harness = next((h for h in get_harnesses() if h.name == name), None)
    if not harness:
        raise HTTPException(status_code=404, detail=f"Unknown harness: {name!r}")
    return harness


@router.get("/session", response_model=AccountResponse, response_model_by_alias=True)
async def get_session(account: Account = Depends(current_account)) -> Account:
    return account


@router.post("/harnesses/{name}/login/start")
async def start_login(name: str, request: Request) -> dict[str, str]:
    harness = _resolve_harness(name)
    account = await resolve_session_account(request)
    url, login_id = await harness.login_start(
        account_id=account.id if account else None,
        proxy_email=proxy_identity(request),
    )
    return {"authorizeUrl": url, "loginId": login_id}


@router.post(
    "/harnesses/{name}/login/complete",
    response_model=AccountResponse,
    response_model_by_alias=True,
)
async def complete_login(
    name: str,
    request: Request,
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
        # A bound reconnect completes only under the session it was started
        # for — a flow surviving its session (eviction, logout, a different
        # sign-in) must never rebind the login by email fallback.
        raise HTTPException(
            status_code=422,
            detail="This sign-in was started under a different session — start it again.",
        )
    # An existing valid session keeps its account; an initial login falls to
    # the trusted proxy identity the flow was started under, else the
    # provider-verified email.
    if session_account:
        account = session_account
    else:
        account = Account.get_or_create(completed.proxy_email or completed.provider_email)
    HarnessLogin.connect(
        harness=harness.name,
        account=account,
        payload=completed.payload,
        expires_at=completed.expires_at,
        provider_email=completed.provider_email,
    )
    old_token = request.cookies.get(sessions.SESSION_COOKIE)
    if old_token:
        # Login rotates any prior session token.
        await sessions.drop_session(old_token)
    request.state.session_token = await sessions.mint_session(account.id)
    return account


@router.post("/logout", status_code=204)
async def logout(request: Request) -> None:
    token = request.cookies.get(sessions.SESSION_COOKIE)
    if token:
        await sessions.drop_session(token)
    request.state.session_token = ""
