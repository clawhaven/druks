from typing import Any

from starlette.datastructures import MutableHeaders

from druks.accounts.sessions import SESSION_COOKIE, SESSION_TTL_SECONDS


class SessionCookieReissue:
    """The single place the session cookie is written. Dependencies and routes
    stamp ``request.state.session_token`` (a fresh or touched token; empty
    string = clear the cookie) and this middleware turns that into a
    Set-Cookie on the response — SSE response headers included. Pure ASGI,
    not BaseHTTPMiddleware, so the streams pass through untouched."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_cookie(message: Any) -> None:
            if message["type"] == "http.response.start":
                # "" clears the cookie (logout); None means untouched.
                token = scope.get("state", {}).get("session_token")
                if token is not None:
                    max_age = SESSION_TTL_SECONDS if token else 0
                    cookie = (
                        f"{SESSION_COOKIE}={token}; HttpOnly; Path=/; "
                        f"SameSite=Lax; Max-Age={max_age}"
                    )
                    # The shipped edge terminates TLS and proxies loopback
                    # HTTP, so the browser endpoint's scheme rides
                    # X-Forwarded-Proto.
                    forwarded = dict(scope.get("headers", ())).get(b"x-forwarded-proto")
                    scheme = forwarded.decode() if forwarded else scope.get("scheme")
                    if scheme == "https":
                        cookie += "; Secure"
                    MutableHeaders(scope=message).append("Set-Cookie", cookie)
            await send(message)

        await self.app(scope, receive, send_with_cookie)
