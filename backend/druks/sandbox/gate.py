import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from druks.redis import get_client

from .constants import MAX_AGENT_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

_ROTATING = "druks:sandbox:rotating"  # set while a rotation holds the gate shut
_RUN_HORIZON = MAX_AGENT_TIMEOUT_SECONDS  # a sandbox run never outlives this; caps every wait
_POLL = 2.0


async def wait_until_open() -> None:
    client = get_client()
    waited = 0.0
    while waited < _RUN_HORIZON and await client.exists(_ROTATING):
        await asyncio.sleep(_POLL)
        waited += _POLL


@asynccontextmanager
async def hold() -> AsyncIterator[None]:
    client = get_client()
    await client.set(_ROTATING, "1", ex=_RUN_HORIZON)

    try:
        await _drain()
        yield
    finally:
        await client.delete(_ROTATING)


async def _drain() -> None:
    # The control plane is the source of truth for live VMs. New ones can't
    # appear while the gate is shut, so the list only shrinks; cap the wait so a
    # host the control plane never reaps can't hold the gate open forever.
    from druks.sandbox.client import sandbox_client

    waited = 0.0
    while waited < _RUN_HORIZON:
        if not await sandbox_client.list_hosts():
            return
        await asyncio.sleep(_POLL)
        waited += _POLL
    logger.warning("sandbox drain hit the horizon with VMs still up; rotating anyway")
