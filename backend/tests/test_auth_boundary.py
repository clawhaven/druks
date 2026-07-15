import pytest
from conftest import configure_app_for_test, make_settings
from druks.accounts.dependencies import current_account
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

# The complete set of API paths allowed to skip the session gate; each carries
# its own authentication or is safe by construction. Anything new that lands
# here is a deliberate decision, not a mounting accident.
EXEMPT_API_PATHS = {
    "/api/system/health",  # health probe
    "/api/auth/harnesses/{name}/login/start",  # the login surface itself
    "/api/auth/harnesses/{name}/login/complete",
    "/api/auth/logout",
    "/api/notifications/{token}/respond",  # capability-authenticated by its token
    "/api/{path:path}",  # the JSON-404 catch-all; reveals nothing
}


@pytest.fixture
def api_routes(tmp_path) -> list[APIRoute]:
    app = configure_app_for_test(settings=make_settings(tmp_path))
    # FastAPI mounts included routers lazily; serving one request materializes
    # the full route table before the walk.
    with TestClient(app) as client:
        client.get("/health")

    found: list[APIRoute] = []

    def walk(routes) -> None:
        for route in routes:
            if isinstance(route, APIRoute):
                found.append(route)
            elif hasattr(route, "routes"):
                walk(route.routes)

    walk(app.router.routes)
    return found


def _session_gated(route: APIRoute) -> bool:
    return any(dependency.call is current_account for dependency in route.dependant.dependencies)


def test_every_internal_api_route_sits_behind_the_session_gate(api_routes):
    unguarded = [
        route.path
        for route in api_routes
        if route.path.startswith("/api/")
        and route.path not in EXEMPT_API_PATHS
        and not _session_gated(route)
    ]
    assert unguarded == []


def test_the_exemptions_are_exactly_the_enumerated_ones(api_routes):
    # The other direction: nothing on the exempt list quietly grew the session
    # gate (a cookie-gated capability route locks out its sessionless callers),
    # and nothing outside /api carries it either.
    for route in api_routes:
        if route.path in EXEMPT_API_PATHS or not route.path.startswith("/api/"):
            assert not _session_gated(route), route.path


def test_webhook_ingress_stays_capability_authenticated(api_routes):
    external = [route for route in api_routes if route.path.startswith("/_external/")]
    assert external, "webhook routes must exist"
    for route in external:
        assert not _session_gated(route), route.path


def test_every_stream_family_is_session_gated(api_routes):
    streams = [route for route in api_routes if route.path.endswith("/stream")]
    # The platform feed plus the generic extension read-sides (transcript,
    # board, subject) — if a family disappears, this list catches the drop.
    assert any(route.path == "/api/events/stream" for route in streams)
    assert any(route.path.endswith("/transcripts/{call_id}/stream") for route in streams)
    for route in streams:
        assert _session_gated(route), route.path
