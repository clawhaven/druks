import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from druks.redis import get_client

from .constants import MAX_AGENT_TIMEOUT_SECONDS

# One gate per credential: rotation runs only while its connection is idle
# (busy defers to the next tick); other connections never block. Active calls
# register in a zset scored by expiry, so a crashed caller ages out.
_RUN_HORIZON = MAX_AGENT_TIMEOUT_SECONDS  # a sandbox run never outlives this; caps every wait
_POLL = 2.0
# The gate is only shut for the seconds a refresh takes; a short TTL means a
# crashed holder frees the login fast instead of blocking it for the horizon.
_SHUT_TTL_SECONDS = 60


def _rotating_key(connection_id: str) -> str:
    return f"druks:sandbox:rotating:{connection_id}"


def _users_key(connection_id: str) -> str:
    return f"druks:sandbox:gate:users:{connection_id}"


@asynccontextmanager
async def use(connection_id: str, call_id: str) -> AsyncIterator[None]:
    """Register the call as an active user of its connection for its span."""
    client = get_client()
    while True:
        waited = 0.0
        while waited < _RUN_HORIZON and await client.exists(_rotating_key(connection_id)):
            await asyncio.sleep(_POLL)
            waited += _POLL
        await client.zadd(_users_key(connection_id), {call_id: time.time() + _RUN_HORIZON})
        # A flag landing between the wait and the add must not race the
        # rotation: back out and re-wait.
        if not await client.exists(_rotating_key(connection_id)):
            break
        await client.zrem(_users_key(connection_id), call_id)
    try:
        yield
    finally:
        await client.zrem(_users_key(connection_id), call_id)


@asynccontextmanager
async def shut(connection_id: str) -> AsyncIterator[bool]:
    """Shut the connection's gate; yield True when idle — rotate now — else
    defer to the next tick. Reopens on exit either way."""
    client = get_client()
    await client.set(_rotating_key(connection_id), "1", ex=_SHUT_TTL_SECONDS)
    try:
        await client.zremrangebyscore(_users_key(connection_id), "-inf", time.time())
        yield not await client.zcard(_users_key(connection_id))
    finally:
        await client.delete(_rotating_key(connection_id))
