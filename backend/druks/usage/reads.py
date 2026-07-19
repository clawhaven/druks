# Usage's shared read helpers: the operator-local day window over finished
# calls and the trend downsampler. The dashboard routes and the agent usage
# service both read through here so every spend-today figure stays identical.
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Row, select

from druks.core.utils.time import operator_local_day
from druks.database import db_session
from druks.durable.models import AgentCall
from druks.usage.schemas import UsageHistoryPoint
from druks.user_settings.models import UserSettings

# Trend ranges for the percent-left sparklines. The 5h window gets one full
# window plus headroom so an exhaustion arc is visible end to end; weekly gets
# the whole week.
FIVE_HOUR_RANGE = timedelta(hours=6)
WEEK_RANGE = timedelta(days=7)

# The agent read keeps each trend this short so the whole response stays
# within its byte budget.
_HISTORY_POINTS = 8


def list_finished_calls_today(account_id: str) -> tuple[ZoneInfo, datetime, list[Row]]:
    # The account's finished calls in the operator-local day, as (timezone,
    # local_start, rows of (model, cost_usd, cost_metadata, finished_at)) —
    # the shared boundary keeps every spend-today figure identical.
    timezone, local_start = operator_local_day(UserSettings.get().timezone, datetime.now(UTC))
    rows = (
        db_session()
        .execute(
            select(
                AgentCall.model,
                AgentCall.cost_usd,
                AgentCall.cost_metadata,
                AgentCall.finished_at,
            )
            .where(AgentCall.account_id == account_id)
            .where(AgentCall.finished_at.is_not(None))
            .where(AgentCall.finished_at >= local_start.astimezone(UTC))
            .where(AgentCall.finished_at < (local_start + timedelta(days=1)).astimezone(UTC)),
        )
        .all()
    )
    return timezone, local_start, rows


def downsample(points: list[UsageHistoryPoint], *, cap: int) -> list[UsageHistoryPoint]:
    # Thin a series to ≤ cap points, always keeping the newest sample (the
    # "now" anchor) — it replaces the last strided sample so the cap holds.
    if len(points) <= cap:
        return points
    stride = -(-len(points) // cap)  # ceil division
    thinned = points[::stride]
    thinned[-1] = points[-1]
    return thinned
