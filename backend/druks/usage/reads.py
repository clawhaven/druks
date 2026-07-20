# Usage's shared read: an account's finished calls in the operator-local day.
# The dashboard routes and the agent usage service both read through here so
# every spend-today figure stays identical.
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Row, select

from druks.core.utils.time import operator_local_day
from druks.database import db_session
from druks.durable.models import AgentCall
from druks.user_settings.models import UserSettings


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
