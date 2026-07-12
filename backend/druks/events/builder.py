from sqlalchemy import or_, select

from druks.database import db_session
from druks.events.feed import FeedItem, generic_entry
from druks.events.models import Event
from druks.extensions.loader import get_extension

_PAGE_LIMIT_DEFAULT = 200
_FETCH_LIMIT = 500


def build_feed(
    *,
    extension: str | None = None,
    before: int | None = None,
    limit: int = _PAGE_LIMIT_DEFAULT,
) -> tuple[list[FeedItem], str | None]:
    items = _render(_events(extension=extension, before=before))
    items.sort(key=lambda e: e.seq, reverse=True)
    page = items[:limit]
    next_cursor = str(page[-1].seq) if len(page) == limit and page else None
    return page, next_cursor


def _events(*, extension: str | None, before: int | None) -> list[Event]:
    # This extension's events plus any unscoped (core) ones. The log stores the extension;
    # the core never derives it from the subject.
    stmt = select(Event).order_by(Event.id.desc())
    if before is not None:
        stmt = stmt.where(Event.id < before)
    if extension is not None:
        stmt = stmt.where(or_(Event.extension == extension, Event.extension.is_(None)))
    return list(db_session().scalars(stmt.limit(_FETCH_LIMIT)).all())


def _render(rows: list[Event]) -> list[FeedItem]:
    # Each event goes to its extension's ``format_event`` hook, so the core stays free
    # of any extension's event types. Resolve each extension once per render; unscoped
    # events (no extension) get a generic item.
    extensions: dict[str | None, object] = {}

    def extension_for(name: str | None):
        if name not in extensions:
            extensions[name] = _resolve_extension(name)
        return extensions[name]

    items: list[FeedItem] = []
    for e in rows:
        m = extension_for(e.extension)
        item = m.format_event(e) if m else generic_entry(e)
        item.seq = e.id  # the builder owns the ordering key, whatever the hook set for id
        items.append(item)
    return items


def _resolve_extension(name: str | None):
    if not name:
        return None
    try:
        return get_extension(name)
    except KeyError:
        return None
