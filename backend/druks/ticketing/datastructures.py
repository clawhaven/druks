from dataclasses import dataclass, field

from .enums import StatusKind


@dataclass
class Ticket:
    """Structured ticket fields the engine reads. Prose (description body,
    comments) isn't normalized here — the agent reads the ticket itself.
    ``description`` is kept for the markdown write-splice (Linear); ``raw`` for
    the ADF write-splice (Jira)."""

    provider: str
    id: str
    key: str
    title: str
    description: str | None = None
    url: str | None = None
    status_name: str | None = None
    status_kind: StatusKind = StatusKind.UNKNOWN
    priority: int | None = None
    assignee_email: str | None = None
    assignee_name: str | None = None
    assignee_id: str | None = None
    project_name: str | None = None
    project_id: str | None = None
    labels: list[str] = field(default_factory=list)
    # The provider container a label or sub-ticket attaches to: Linear team,
    # Jira project.
    container_id: str | None = None
    container_name: str | None = None
    raw: dict = field(default_factory=dict)

    def has_label(self, name: str) -> bool:
        return name in self.labels

    @classmethod
    def ref(cls, provider: str, key: str) -> "Ticket":
        # Status and comment endpoints accept the key as id, so key-only
        # operations skip the fetch.
        return cls(provider=provider, id=key, key=key, title="")
