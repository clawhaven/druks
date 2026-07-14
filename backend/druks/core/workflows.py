import contextlib
import logging

from druks.harnesses.datastructures import RotationResult
from druks.harnesses.registry import get_harnesses
from druks.sandbox import gate
from druks.workflows import Workflow

logger = logging.getLogger(__name__)


class RefreshTokens(Workflow):
    every = "*/15 * * * *"

    async def run(self) -> dict[str, object]:
        # Every 15 min. With an ~8h Claude TTL refreshed at <2h remaining (and
        # codex ~10d at <24h), this keeps both tokens alive with a wide margin
        # while doing almost nothing on most ticks.
        return await _refresh()


async def _refresh() -> dict[str, object]:
    harnesses = get_harnesses()

    # rotate_token is the source of truth for what's due: it no-ops ("fresh", no
    # server call, no invalidation) any harness outside its margin, so rotating
    # all only refreshes the one(s) actually expiring. A refresh invalidates the
    # old token server-side and would 401 a VM mid-run holding a pushed copy,
    # so close the gate around it — but only when a rotation is
    # coming, since the common no-op tick shouldn't stall provisioning.
    coming = any(harness.needs_refresh() for harness in harnesses)
    gate_ctx = gate.hold() if coming else contextlib.nullcontext()

    results: list[RotationResult] = []
    async with gate_ctx:
        for harness in harnesses:
            result = await harness.rotate_token()
            _log_result(result)
            results.append(result)

    return {
        "results": [{"harness": r.harness, "action": r.action, "error": r.error} for r in results],
    }


def _log_result(result: RotationResult) -> None:
    if result.action == "refreshed":
        logger.info("refreshed %s token; expires_at=%s", result.harness, result.expires_at)
    elif result.action == "failed" and result.error != "no_credentials":
        # invalid_grant => operator must re-login; network/http_* => transient.
        # no_credentials is a disconnected harness, not a failure — stay quiet so
        # a deliberately-disconnected harness doesn't warn every tick.
        logger.warning("token refresh failed for %s: %s", result.harness, result.error)
    elif result.action == "no_refresh_token":
        logger.warning("%s credential has no refresh token; cannot keep it alive", result.harness)
    # "fresh" and no_credentials are quiet no-ops.
