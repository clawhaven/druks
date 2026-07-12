from enum import StrEnum


class StatusKind(StrEnum):
    BACKLOG = "backlog"
    STARTED = "started"
    REVIEW = "review"
    DONE = "done"
    CANCELED = "canceled"
    UNKNOWN = "unknown"


class SemanticStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    CANCELED = "canceled"
    READY_FOR_AGENT = "ready_for_agent"
