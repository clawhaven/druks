import pytest
from druks.accounts.dependencies import current_account, current_session_account
from druks.api.app import app
from fastapi.routing import APIRoute, _IncludedRouter

# Every /api path allowed to skip the session gate; additions are deliberate.
EXEMPT_API_PATHS = {
    "/api/system/health",
    "/api/auth/harnesses/{name}/login/start",
    "/api/auth/harnesses/{name}/login/complete",
    "/api/auth/logout",
    "/api/{path:path}",  # the JSON-404 catch-all
}

# PAT management admits the session cookie only — never a PAT, so a token
# cannot mint or revoke tokens.
SESSION_ONLY_API_PATHS = {
    "/api/auth/pats",
    "/api/auth/pats/{pat_id}",
}


def _walk(routes):
    # FastAPI 0.139 defers include_router into _IncludedRouter nodes; only
    # effective_candidates() shows the include-time dependencies (the gate).
    for route in routes:
        if isinstance(route, _IncludedRouter):
            yield from _walk(route.effective_candidates())
        elif isinstance(route, APIRoute) or isinstance(
            getattr(route, "original_route", None), APIRoute
        ):
            yield route
        elif hasattr(route, "routes"):
            yield from _walk(route.routes)


@pytest.fixture
def api_routes():
    return list(_walk(app.router.routes))


def _gated_by(route, gate) -> bool:
    return any(dependency.call is gate for dependency in route.dependant.dependencies)


def test_every_internal_api_route_sits_behind_the_session_gate(api_routes):
    unguarded = [
        route.path
        for route in api_routes
        if route.path.startswith("/api/")
        and route.path not in EXEMPT_API_PATHS
        and route.path not in SESSION_ONLY_API_PATHS
        and not _gated_by(route, current_account)
    ]
    assert unguarded == []
    # The sweep only covers the stream families if they exist; pin that.
    paths = {route.path for route in api_routes}
    assert "/api/events/stream" in paths
    assert any(path.endswith("/transcripts/{call_id}/stream") for path in paths)


def test_the_exemptions_are_exactly_the_enumerated_ones(api_routes):
    # The other direction: nothing exempt or outside /api carries the gate.
    for route in api_routes:
        if route.path in EXEMPT_API_PATHS or not route.path.startswith("/api/"):
            assert not _gated_by(route, current_account), route.path
    assert any(route.path.startswith("/_external/") for route in api_routes)


def test_pat_management_is_session_only(api_routes):
    listed = [route for route in api_routes if route.path in SESSION_ONLY_API_PATHS]
    assert {route.path for route in listed} == SESSION_ONLY_API_PATHS
    for route in listed:
        assert _gated_by(route, current_session_account), route.path
        assert not _gated_by(route, current_account), route.path
    # And nothing else carries the session-only gate.
    for route in api_routes:
        if route.path not in SESSION_ONLY_API_PATHS:
            assert not _gated_by(route, current_session_account), route.path
