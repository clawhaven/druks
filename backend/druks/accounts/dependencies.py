from fastapi import HTTPException, Request

from druks.accounts import sessions
from druks.accounts.models import Account


async def resolve_session_account(request: Request) -> Account | None:
    """The account the request's session cookie speaks for, touching the
    sliding TTL — or None. Drops the session when its account is gone or a
    trusted proxy identity no longer matches it."""
    token = request.cookies.get(sessions.SESSION_COOKIE)
    if not token:
        return None
    account_id = await sessions.resolve_session(token)
    if not account_id:
        return None
    account = Account.get(account_id)
    if not account:
        await sessions.drop_session(token)
        return None
    proxy_email = proxy_identity(request)
    if proxy_email and proxy_email != account.email:
        # The trusted identity in front of us moved on; this cookie no longer
        # speaks for its account.
        await sessions.drop_session(token)
        return None
    # SessionCookieReissue turns this into a refreshed Set-Cookie on the way out.
    request.state.session_token = token
    return account


async def current_account(request: Request) -> Account:
    """Route dependency: the signed-in account, else 401. Identity resolvers
    line up here — a future bearer/PAT resolver slots in beside the session
    one without touching route dependencies."""
    account = await resolve_session_account(request)
    if not account:
        raise HTTPException(status_code=401, detail="Sign in to use this API.")
    return account


def proxy_identity(request: Request) -> str | None:
    """The trusted proxy's identity header value, normalized — None when no
    proxy injects one (local installs, or the header name configured empty)."""
    header = request.app.state.settings.auth_header
    if not header:
        return None
    value = request.headers.get(header, "")
    if not value.strip():
        return None
    return Account.normalize_email(value)
