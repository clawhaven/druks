import hashlib
import hmac

from fastapi import HTTPException, status


def verify_hmac_sha256(
    raw_body: bytes,
    signature: str | None,
    secret: str,
    *,
    prefix: str = "sha256=",
) -> None:
    """Verify a GitHub-style HMAC-SHA256 signature header.

    Raises ``HTTPException`` directly so handlers can call this inline
    from ``request_is_authentic``.
    """
    if not secret:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Webhook secret is not set.",
        )
    if not signature:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing webhook signature.",
        )

    expected = prefix + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid webhook signature.",
        )
