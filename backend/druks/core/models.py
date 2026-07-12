from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from uuid_utils import uuid7


def uuid7_str() -> str:
    return str(uuid7())


class Uuid7Pk:
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid7_str)
