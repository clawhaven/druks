import secrets

from druks.redis import get_client

SESSION_COOKIE = "druks_session"
SESSION_TTL_SECONDS = 30 * 24 * 3600


def _session_key(token: str) -> str:
    return f"druks:session:{token}"


async def mint_session(account_id: str) -> str:
    token = secrets.token_urlsafe(32)
    await get_client().set(_session_key(token), account_id, ex=SESSION_TTL_SECONDS)
    return token


async def resolve_session(token: str) -> str | None:
    # GETEX reads and slides the 30-day TTL in one atomic hop.
    value = await get_client().getex(_session_key(token), ex=SESSION_TTL_SECONDS)
    if not value:
        return None
    return value.decode()


async def drop_session(token: str) -> None:
    await get_client().delete(_session_key(token))
