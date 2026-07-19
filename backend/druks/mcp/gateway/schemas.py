from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from druks.durable.schemas import AgentCallSummary, TextSlice
from druks.schemas import BaseResponse
from druks.usage.schemas import UsageHistoryPoint


class ArtifactChunk(BaseResponse):
    # A call's renderable output, head-bounded; page the rest through the
    # call's transcript files route.
    call_id: str
    kind: str
    title: str
    chunk: TextSlice


class GateView(BaseResponse):
    # Everything needed to answer a parked run in one read: the ask, the
    # artifact under review, the reply's JSON Schema, and parked_at — the park
    # identity answer_gate must echo back.
    run_id: str
    gate: str
    parked_at: datetime
    ask: dict[str, Any]
    artifact: ArtifactChunk | None = None
    reply_schema: dict[str, Any]


class GateAnswerResult(BaseResponse):
    run_id: str
    parked_at: datetime
    result: Literal["answered", "already_answered"]


class AgentCallDetail(BaseResponse):
    run_id: str
    call: AgentCallSummary
    transcript: TextSlice
    stderr: TextSlice
    artifact: ArtifactChunk | None = None


class CancelRunResult(BaseResponse):
    run_id: str
    result: Literal["cancelled", "already_cancelled"]


class AgentHarnessUsage(BaseResponse):
    # One harness's quota for the agent surface: the latest snapshot's facts
    # plus a short percent-left trend per window, oldest first.
    name: str
    is_connected: bool = False
    plan_tier: str | None = None
    five_hour_percent_left: int | None = None
    five_hour_resets_at: datetime | None = None
    week_percent_left: int | None = None
    week_resets_at: datetime | None = None
    is_unlimited: bool = False
    scraped_at: datetime | None = None
    five_hour_history: list[UsageHistoryPoint] = Field(default_factory=list)
    week_history: list[UsageHistoryPoint] = Field(default_factory=list)


class AgentUsage(BaseResponse):
    # The caller's spend for the operator-local day plus per-harness quota.
    day: str
    timezone: str
    spend_today_usd: float
    tokens_today: int
    runs_today: int
    harnesses: list[AgentHarnessUsage] = Field(default_factory=list)
