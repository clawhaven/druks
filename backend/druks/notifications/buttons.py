import base64
import binascii

from druks.notifications.exceptions import MalformedButtonError


def encode_button(token: str, choice_id: str) -> str:
    # base64url keeps the id opaque and URL-safe for any token/choice alphabet,
    # and "." can never appear inside an encoded part, so the split point is
    # unambiguous and distinct pairs can't collide.
    return f"{_encode_part(token)}.{_encode_part(choice_id)}"


def decode_button(action_id: str) -> tuple[str, str]:
    # The action_id arrives in an untrusted webhook payload; a non-string is
    # malformed input, not a crash.
    if not isinstance(action_id, str):
        raise MalformedButtonError()
    token_part, separator, choice_part = action_id.partition(".")
    if not separator:
        raise MalformedButtonError()
    try:
        return _decode_part(token_part), _decode_part(choice_part)
    except (binascii.Error, UnicodeDecodeError) as error:
        raise MalformedButtonError() from error


def _encode_part(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def _decode_part(part: str) -> str:
    padded = part + "=" * (-len(part) % 4)
    # validate=True: without it b64decode silently discards foreign characters
    # instead of rejecting a tampered id.
    return base64.b64decode(padded, altchars=b"-_", validate=True).decode()
