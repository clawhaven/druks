from datetime import UTC, datetime

from druks.redis import get_client

_DEDUP_TTL_SECONDS = 24 * 60 * 60


def _seen_key(provider: str, key: str) -> str:
    return f"druks:webhook:seen:{provider}:{key}"


async def mark_delivery(provider: str, key: str | None) -> bool:
    """A duplicate still bumps freshness — a replay proves the pipe works."""
    client = get_client()
    await client.set(f"druks:webhook:last:{provider}", datetime.now(UTC).isoformat())
    if key is None:
        return True
    return bool(await client.set(_seen_key(provider, key), "1", nx=True, ex=_DEDUP_TTL_SECONDS))


async def release_delivery(provider: str, key: str | None) -> None:
    # Undo the dedup claim when the handler failed, so the provider's retry re-processes
    # instead of hitting on_duplicate for the whole dedup TTL. Freshness stays bumped —
    # the delivery did arrive.
    if key is None:
        return
    await get_client().delete(_seen_key(provider, key))


async def last_delivery_at(provider: str) -> datetime | None:
    raw = await get_client().get(f"druks:webhook:last:{provider}")
    return datetime.fromisoformat(raw.decode()) if raw else None
