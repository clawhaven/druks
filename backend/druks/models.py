from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from druks.core.utils.time import ensure_utc


class _UtcDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        return ensure_utc(value) if value else value


class Base(DeclarativeBase):
    # Every ``Mapped[datetime]`` column stores tz-aware UTC — the decorator
    # guarantees aware values on read (writes are unaffected). Mapping it here
    # means models declare ``Mapped[datetime]`` with no per-column type.
    type_annotation_map = {datetime: _UtcDateTime()}

    @staticmethod
    def utc_now() -> datetime:
        return datetime.now(UTC).replace(microsecond=0)
