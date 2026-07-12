from typing import Any, Literal, get_args, get_origin

from pydantic import BaseModel, SecretStr, ValidationError
from pydantic.fields import FieldInfo

from .exceptions import SettingsDeclarationError

# A declared field's Python annotation picks its wire kind, which is the only thing
# the frontend switches on to choose an input control (checkbox / number / text /
# select / password). ``SecretStr`` and a ``Literal`` choice set are the two rich
# kinds an author reaches for beyond the scalars.
_SCALAR_KINDS: dict[type, str] = {bool: "bool", int: "int", str: "str"}


def _declares_secret(annotation: object) -> bool:
    # ``SecretStr`` anywhere in the annotation tree marks the field secret — bare, in a
    # union (``SecretStr | None``), or in a container (``list[SecretStr]``) — so a
    # secret can't slip through as a plaintext value from any shape it's declared in.
    if annotation is SecretStr:
        return True
    return any(_declares_secret(arg) for arg in get_args(annotation))


def _literal_members(annotation: object) -> tuple[Any, ...] | None:
    # The choices of a ``Literal`` field, unwrapping an ``Optional``/union so
    # ``Literal["a", "b"] | None`` — and a union of separate literals like
    # ``Literal["a"] | Literal["b"]`` — is still recognized. None when the field
    # declares no literal. Members keep their declared type (str, int, …).
    if get_origin(annotation) is Literal:
        return get_args(annotation)
    members = [member for arg in get_args(annotation) for member in (_literal_members(arg) or ())]
    return tuple(members) if members else None


def field_kind(field: FieldInfo) -> str:
    annotation = field.annotation
    if _declares_secret(annotation):
        return "secret"
    if _literal_members(annotation):
        return "enum"
    if isinstance(annotation, type):
        return _SCALAR_KINDS.get(annotation, "str")
    return "str"


def field_choices(field: FieldInfo) -> list[str] | None:
    # An enum's closed choice set, surfaced so the UI renders a select. The wire is
    # always strings (the select submits ``e.target.value``); ``coerce_setting_value``
    # maps a submitted string back to the member's declared type on the way in.
    members = _literal_members(field.annotation)
    if not members:
        return None
    return [str(member) for member in members]


def _nested_model(annotation: object) -> type[BaseModel] | None:
    # A ``BaseModel`` anywhere in the annotation tree — the one shape the flat settings
    # plane can't render or key by. ``SecretStr`` is a str, not a model, so it's clear.
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    for arg in get_args(annotation):
        if nested := _nested_model(arg):
            return nested
    return None


def validate_settings_declaration(model: type[BaseModel]) -> None:
    # A settings field is a scalar, a ``SecretStr``, a ``Literal``, or an Optional /
    # container of those — never a nested model. Reject a nested model at declaration so
    # a shape the plane can't render (or safely redact) fails loudly where it's written
    # rather than at the first operator PATCH.
    for name, field in model.model_fields.items():
        if nested := _nested_model(field.annotation):
            raise SettingsDeclarationError(
                f"settings field {name!r}: nested models are not a supported settings "
                f"shape (found {nested.__name__}); declare scalar, SecretStr, or Literal fields"
            )


def coerce_setting_value(model: type[BaseModel], field: str, value: Any) -> Any:
    # A select submits every choice as a string, but a ``Literal`` may hold ints or
    # bools — map the submitted string back to the member it names so validation sees
    # the declared type. Leaves non-enum fields and already-typed values untouched.
    if not isinstance(value, str):
        return value
    field_info = model.model_fields.get(field)
    if not field_info:
        return value
    members = _literal_members(field_info.annotation)
    if not members:
        return value
    return next((member for member in members if str(member) == value), value)


def validate_setting_override(
    model: type[BaseModel], current: dict[str, Any], field: str, value: Any
) -> None:
    # Merge the new value onto the currently-resolved settings and validate the whole
    # model, so cross-field validators run against real state (not a blank shell of
    # defaults). ``current`` is already a valid, resolved settings dump, so a sibling
    # can't spuriously fail. On failure, raise a ValueError whose message is redacted —
    # never the submitted input, and never a secret field's raw value — so a rejected
    # secret can't ride out in the 422 body.
    try:
        model.model_validate({**current, field: value})
    except ValidationError as error:
        raise ValueError(_redacted_validation_message(model, error)) from error


def _redacted_validation_message(model: type[BaseModel], error: ValidationError) -> str:
    # Pydantic's ``str(ValidationError)`` (and each error's ``input``/``ctx``/``url``)
    # echoes the submitted value — a secret leak — so rebuild from the safe keys only.
    # ``msg`` is safe for a built-in error, but a custom validator can embed the raw
    # value in it: drop ``msg`` for a secret field's error (and any model-level error,
    # where a validator saw every field, secrets included) in favor of a generic line.
    parts = []
    for detail in error.errors():
        location = tuple(detail["loc"])
        label = ".".join(str(part) for part in location) or "(value)"
        if _touches_secret(model, location):
            parts.append(f"{label}: invalid value")
        else:
            parts.append(f"{label}: {detail['msg']}")
    return "; ".join(parts)


def _touches_secret(model: type[BaseModel], location: tuple[Any, ...]) -> bool:
    # A field-level error names its field first; redact when that field is a secret. A
    # model-level error has an empty location — a model validator can read every field,
    # so redact whenever the model declares any secret at all.
    fields = model.model_fields
    if not location:
        return any(field_kind(info) == "secret" for info in fields.values())
    field = location[0]
    return isinstance(field, str) and field in fields and field_kind(fields[field]) == "secret"
