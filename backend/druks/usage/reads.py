# Usage's shared read: an account's finished calls in a time window, as rows of
# (model, cost_usd, cost_metadata, finished_at). The caller passes the
# operator-local-day window, so every spend-today figure counts the same calls.
from datetime import datetime

from sqlalchemy import Row, select

from druks.database import db_session
from druks.durable.models import AgentCall


def list_finished_calls(account_id: str, *, since: datetime, until: datetime) -> list[Row]:
    return list(
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
            .where(AgentCall.finished_at >= since)
            .where(AgentCall.finished_at < until)
        )
        .all()
    )
