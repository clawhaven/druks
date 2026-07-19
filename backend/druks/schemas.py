import json

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class BaseResponse(BaseModel):
    # Read-side response base: snake_case fields serialize to camelCase for the
    # frontend, so a shape doesn't hand-write serialization_alias on every field.
    # Output-only — request bodies use alias= for input and don't inherit this.
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def _wire_cost(char: str) -> int:
    # What one character spends of a wire budget: its JSON-escaped UTF-8 bytes
    # (a control byte like ESC serializes as  — six bytes, not one).
    return len(json.dumps(char, ensure_ascii=False).encode()) - 2


def clip(text: str | None, limit: int) -> str | None:
    # Budgeted read-sides bound their free-text fields by what the field will
    # occupy in the serialized response, so the budgets hold for multibyte and
    # escape-heavy text alike. The ellipsis (3 bytes) marks the cut.
    if not text:
        return text
    total = 0
    cut = None
    for index, char in enumerate(text):
        total += _wire_cost(char)
        if cut is None and total > limit - 3:
            cut = index
        if total > limit:
            return text[:cut] + "…"
    return text


__all__ = ["BaseResponse"]
