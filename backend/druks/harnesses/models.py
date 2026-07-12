from datetime import datetime

from sqlalchemy import JSON, String, delete
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm.attributes import flag_modified

from druks.database import db_session
from druks.models import Base

# store()'s ``account`` sentinel: rotation/import leave the label the connect
# flow set alone; only the connect flow passes an explicit account.
_KEEP_ACCOUNT: str = "\x00keep-account"


class HarnessLogin(Base):
    __tablename__ = "harness_logins"

    harness: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, default="subscription")
    payload: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[datetime | None]
    account: Mapped[str | None]
    updated_at: Mapped[datetime] = mapped_column(default=Base.utc_now, onupdate=Base.utc_now)

    @classmethod
    def get(cls, harness: str) -> "HarnessLogin | None":
        return db_session().get(cls, harness)

    @classmethod
    def store(
        cls,
        *,
        harness: str,
        payload: dict,
        expires_at: datetime | None,
        account: str | None = _KEEP_ACCOUNT,
    ) -> None:
        """Upsert the harness row's payload + expiry. ``account`` defaults to
        keep-what's-there so a rotation tick never wipes the label the connect
        flow set; the connect flow passes it explicitly."""
        session = db_session()
        row = session.get(cls, harness)
        if row:
            row.payload = payload
            # rotate_token loads this row, mutates the payload dict in place, and
            # hands the same object back — a JSON column can't see a same-identity
            # change, so persisting it would ride on another column happening to
            # change too. Flag it so the refreshed token is written on its own
            # merit; this is a secrets store, not somewhere to lose a token.
            flag_modified(row, "payload")
            row.expires_at = expires_at
            if account != _KEEP_ACCOUNT:
                row.account = account
        else:
            row = cls(
                harness=harness,
                payload=payload,
                expires_at=expires_at,
                account=None if account == _KEEP_ACCOUNT else account,
            )
            session.add(row)
        session.flush()

    @classmethod
    def delete(cls, harness: str) -> None:
        session = db_session()
        session.execute(delete(cls).where(cls.harness == harness))
        session.flush()
