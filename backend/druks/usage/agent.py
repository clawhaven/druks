# Usage's half of the agent surface: one pure read of the caller's quota and
# today's spend — no poll trigger; refresh stays route-driven.
from datetime import UTC, datetime

from druks.accounts.models import Account
from druks.harnesses.artifacts import normalize_token_usage
from druks.harnesses.models import HarnessConnection
from druks.harnesses.registry import get_harnesses
from druks.schemas import clip
from druks.usage.models import UsageScrape
from druks.usage.reads import (
    _HISTORY_POINTS,
    FIVE_HOUR_RANGE,
    WEEK_RANGE,
    downsample,
    list_finished_calls_today,
)
from druks.usage.schemas import AgentHarnessUsage, AgentUsage, UsageHistoryPoint


def get_usage(account: Account) -> AgentUsage:
    now = datetime.now(UTC)
    timezone, local_start, rows = list_finished_calls_today(account.id)
    spend = 0.0
    tokens = 0
    for _, cost_usd, cost_metadata, _ in rows:
        if cost_usd is not None:
            spend += float(cost_usd)
        usage = normalize_token_usage(cost_metadata)
        if usage:
            tokens += usage["total_tokens"]
    return AgentUsage(
        day=local_start.date().isoformat(),
        timezone=str(timezone),
        spend_today_usd=round(spend, 4),
        tokens_today=tokens,
        runs_today=len(rows),
        harnesses=[_harness_usage(h.name, account.id, now=now) for h in get_harnesses()],
    )


def _harness_usage(name: str, account_id: str, *, now: datetime) -> AgentHarnessUsage:
    is_connected = bool(HarnessConnection.get_for_account(name, account_id))
    row = UsageScrape.latest_for(name, account_id)
    if not row:
        return AgentHarnessUsage(name=name, is_connected=is_connected)
    history = UsageScrape.history_for(name, account_id, since=now - WEEK_RANGE)
    five_hour_cutoff = now - FIVE_HOUR_RANGE
    five_hour = [
        UsageHistoryPoint(t=point.scraped_at, pct=point.five_hour_percent_left)
        for point in history
        if point.five_hour_percent_left is not None and point.scraped_at >= five_hour_cutoff
    ]
    week = [
        UsageHistoryPoint(t=point.scraped_at, pct=point.week_percent_left)
        for point in history
        if point.week_percent_left is not None
    ]
    return AgentHarnessUsage(
        name=name,
        is_connected=is_connected,
        plan_tier=clip(row.plan_tier, 64),
        five_hour_percent_left=row.five_hour_percent_left,
        five_hour_resets_at=row.five_hour_resets_at,
        week_percent_left=row.week_percent_left,
        week_resets_at=row.week_resets_at,
        is_unlimited=row.unlimited,
        scraped_at=row.scraped_at,
        five_hour_history=downsample(five_hour, cap=_HISTORY_POINTS),
        week_history=downsample(week, cap=_HISTORY_POINTS),
    )
