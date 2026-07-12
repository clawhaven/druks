from typing import Any

from druks.core.apis.exceptions import GitHubAppNotInstalledError
from druks.core.apis.github import GitHubClient


class _Parsed:
    def model_dump(self) -> dict[str, str]:
        return {"id": "review-1"}


class _Response:
    parsed_data = _Parsed()


class _Pulls:
    def __init__(self) -> None:
        self.create_review_kwargs: dict[str, Any] | None = None

    async def async_create_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        **kwargs: Any,
    ) -> _Response:
        self.create_review_kwargs = {
            "owner": owner,
            "repo": repo,
            "pr_number": pr_number,
            **kwargs,
        }
        return _Response()


class _Rest:
    def __init__(self) -> None:
        self.pulls = _Pulls()


class _GitHub:
    def __init__(self) -> None:
        self.rest = _Rest()


class _TestGitHubClient(GitHubClient):
    def __init__(self, gh: _GitHub) -> None:
        self.gh = gh

    async def _for_repo(self, repo: str) -> Any:
        return self.gh


async def test_create_review_omits_empty_comments() -> None:
    gh = _GitHub()
    client = _TestGitHubClient(gh)

    await client.create_review(
        "ClawHaven/example",
        7,
        event="APPROVE",
        body="Approved.",
    )

    assert gh.rest.pulls.create_review_kwargs == {
        "owner": "ClawHaven",
        "repo": "example",
        "pr_number": 7,
        "event": "APPROVE",
        "body": "Approved.",
    }


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def _make_request_failed(status_code: int):
    from githubkit.exception import RequestFailed

    exc = RequestFailed.__new__(RequestFailed)
    exc.response = _FakeResponse(status_code)  # type: ignore[assignment]
    return exc


class _Flaky401Pulls:
    def __init__(self) -> None:
        self.calls = 0

    async def async_update(self, owner: str, repo: str, pr_number: int, **kwargs: Any):
        self.calls += 1
        if self.calls == 1:
            raise _make_request_failed(401)
        return _Response()


class _ForbiddenPulls:
    def __init__(self) -> None:
        self.calls = 0

    async def async_update(self, owner: str, repo: str, pr_number: int, **kwargs: Any):
        self.calls += 1
        raise _make_request_failed(403)


class _StuckOn401Pulls:
    def __init__(self) -> None:
        self.calls = 0

    async def async_update(self, owner: str, repo: str, pr_number: int, **kwargs: Any):
        self.calls += 1
        raise _make_request_failed(401)


class _CountingForRepoClient(GitHubClient):
    def __init__(self, gh_factory) -> None:
        self.gh_factory = gh_factory
        self.for_repo_calls = 0
        self.invalidate_calls = 0

    async def _for_repo(self, repo: str) -> Any:
        self.for_repo_calls += 1
        return self.gh_factory()

    async def _invalidate_for_repo(self, repo: str) -> None:
        self.invalidate_calls += 1


async def test_401_invalidates_cache_and_retries_once_then_succeeds() -> None:
    pulls = _Flaky401Pulls()

    class _Gh:
        def __init__(self) -> None:
            self.rest = type("R", (), {"pulls": pulls})()

    gh = _Gh()
    client = _CountingForRepoClient(lambda: gh)

    # No exception — the second attempt succeeds.
    await client.update_pull_request_body("ClawHaven/example", 7, "new body")

    assert pulls.calls == 2
    assert client.invalidate_calls == 1
    assert client.for_repo_calls == 2  # initial + post-invalidate


async def test_403_does_not_retry() -> None:
    from githubkit.exception import RequestFailed

    pulls = _ForbiddenPulls()

    class _Gh:
        def __init__(self) -> None:
            self.rest = type("R", (), {"pulls": pulls})()

    client = _CountingForRepoClient(lambda: _Gh())

    try:
        await client.update_pull_request_body("ClawHaven/example", 7, "new body")
    except RequestFailed:
        pass
    else:
        raise AssertionError("expected RequestFailed to propagate")

    assert pulls.calls == 1
    assert client.invalidate_calls == 0


async def test_401_on_retry_surfaces_to_caller() -> None:
    from githubkit.exception import RequestFailed

    pulls = _StuckOn401Pulls()

    class _Gh:
        def __init__(self) -> None:
            self.rest = type("R", (), {"pulls": pulls})()

    client = _CountingForRepoClient(lambda: _Gh())

    try:
        await client.update_pull_request_body("ClawHaven/example", 7, "new body")
    except RequestFailed as exc:
        assert exc.response.status_code == 401
    else:
        raise AssertionError("expected RequestFailed to propagate")

    assert pulls.calls == 2
    assert client.invalidate_calls == 1


async def test_token_for_repo_retries_on_401_and_succeeds() -> None:
    calls = {"n": 0}

    class _AppApps:
        async def async_create_installation_access_token(self, _id: int) -> Any:
            calls["n"] += 1
            if calls["n"] == 1:
                raise _make_request_failed(401)

            class _Tok:
                class parsed_data:
                    token = "ghs_fresh_token"

            return _Tok()

    class _AppGitHub:
        rest = type("R", (), {"apps": _AppApps()})()

    class _Client(GitHubClient):
        def __init__(self) -> None:
            self._app = _AppGitHub()
            self._installation_cache: dict[str, int] = {"ClawHaven/example": 12345}
            self._repo_gh_cache: dict[int, Any] = {}
            self.invalidated: list[str] = []

        async def _installation_id(self, repo: str) -> int:
            return self._installation_cache.get(repo, 99999)

        async def _invalidate_for_repo(self, repo: str) -> None:
            self.invalidated.append(repo)
            self._installation_cache.pop(repo, None)

    client = _Client()
    token = await client.token_for_repo("ClawHaven/example")

    assert token == "ghs_fresh_token"
    assert calls["n"] == 2
    assert client.invalidated == ["ClawHaven/example"]


async def test_github_client_aclose_drops_cache_without_raising() -> None:
    """``aclose()`` must not call githubkit's ``__aexit__`` — these clients are
    used via direct calls (per-request self-closing httpx clients), so the
    contextvar holding a long-lived client is always None and ``__aexit__``
    would raise ``'NoneType' object has no attribute 'aclose'`` (the prod
    "Application shutdown failed" on every restart). aclose just drops the
    per-installation cache."""
    from githubkit import GitHub

    client = GitHubClient.__new__(GitHubClient)
    client._app = GitHub("fake-token")
    client._repo_gh_cache = {1: GitHub("fake-token")}

    await client.aclose()  # must not raise
    assert client._repo_gh_cache == {}


async def test_get_file_content_returns_none_when_repo_missing() -> None:
    """A 404 at the installation lookup (the repo doesn't exist / the Extension
    isn't installed) means the file doesn't exist either — so get_file_content
    returns None rather than raising. This is the prompt-override hierarchy
    probing a missing ``<owner>/.druks`` repo: it must fall through to the
    bundled prompt, not blow up the operation (prod scope 404 regression)."""

    class _RepoMissingClient(GitHubClient):
        def __init__(self) -> None:  # skip real auth
            pass

        async def _for_repo(self, repo: str) -> Any:
            raise _make_request_failed(404)

    client = _RepoMissingClient()
    assert await client.get_file_content("clawhaven/.druks", "prompts/x.md") is None


async def test_installation_lookup_404_names_the_repo() -> None:
    """An App without access to the repo fails every call at the installation
    lookup. The raw githubkit repr (``Response(404 Not Found, …)``) is what a
    run's failure column would show the operator — translate it into an error
    that names the repo and the fix."""

    class _Apps:
        async def async_get_repo_installation(self, owner: str, name: str) -> Any:
            raise _make_request_failed(404)

    class _UninstalledClient(GitHubClient):
        def __init__(self) -> None:  # skip real auth
            self._installation_cache = {}
            self._app = type("_App", (), {"rest": type("_Rest", (), {"apps": _Apps()})()})()

    client = _UninstalledClient()
    try:
        await client._installation_id("ClawHaven/acme-app")
    except GitHubAppNotInstalledError as error:
        assert "ClawHaven/acme-app" in str(error)
        assert "install the app" in str(error)
    else:
        raise AssertionError("expected GitHubAppNotInstalledError")


async def test_get_file_content_returns_none_when_app_not_installed() -> None:
    # Same optional-read contract as the raw-404 case above: an unreachable
    # repo has no file to read.
    class _UninstalledClient(GitHubClient):
        def __init__(self) -> None:  # skip real auth
            pass

        async def _for_repo(self, repo: str) -> Any:
            raise GitHubAppNotInstalledError(repo)

    client = _UninstalledClient()
    assert await client.get_file_content("clawhaven/.druks", "prompts/x.md") is None
