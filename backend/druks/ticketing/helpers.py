from collections.abc import Callable

from druks.settings import load_settings

from . import jira, linear
from .base import Tracker

_PROVIDERS: dict[str, Callable[..., Tracker]] = {
    linear.Linear.source: linear.Linear.from_settings,
    jira.Jira.source: jira.Jira.from_settings,
}


def is_tracker_source(source: str) -> bool:
    return source in _PROVIDERS


def get_tracker(source: str, *, ready_for_agent_status: str = "") -> Tracker:
    # KeyErrors on a source that isn't a tracker — guard with is_tracker_source
    # first when the source might not be one (e.g. github). ``ready_for_agent_status``
    # is the operator's name for the READY_FOR_AGENT status; empty leaves it unmapped.
    # Caller owns the lifecycle: `async with get_tracker(...)`.
    return _PROVIDERS[source](ready_for_agent_status=ready_for_agent_status)


def configured_source() -> str | None:
    # Mirrors each provider's from_settings credential guard without
    # instantiating one (the constructors build HTTP clients).
    settings = load_settings()
    if settings.linear_api_key:
        return linear.Linear.source
    if settings.jira_base_url and settings.jira_email and settings.jira_api_token:
        return jira.Jira.source
    return None
