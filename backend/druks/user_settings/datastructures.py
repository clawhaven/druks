from typing import Literal, NamedTuple

ALLOWED_EFFORTS: tuple[str, ...] = ("low", "medium", "high")

# agent: per-agent override; declared: the agent's own field; harness: the
# agent's harness default (claude/codex effort + timeout).
_SettingSource = Literal["agent", "declared", "harness"]


class ResolvedModel(NamedTuple):
    value: str
    source: Literal["agent", "default"]


class ResolvedEffort(NamedTuple):
    value: str
    source: _SettingSource


class ResolvedTimeout(NamedTuple):
    value: int
    source: _SettingSource
