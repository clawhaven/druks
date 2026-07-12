class GitHubAppNotInstalledError(Exception):
    """The GitHub App has no installation covering the repo — it was never
    installed there, the repo isn't in the installation's selected
    repositories, or the repo doesn't exist. The message names the repo so a
    run failure surfaces the actionable cause, not githubkit's response repr."""

    def __init__(self, repo: str) -> None:
        super().__init__(
            f"The GitHub App has no access to {repo} — install the app on the "
            "repo (or add it to the installation's selected repositories)."
        )
        self.repo = repo


class GitHubAppNotConfiguredError(Exception):
    """Operator or reviewer GitHub App credentials are absent from settings;
    the message names the env vars to set."""


class JiraAPIError(Exception):
    """Jira REST returned a non-2xx response. Distinct from ``httpx.HTTPError``
    (transport) so callers can ``except (httpx.HTTPError, JiraAPIError)``."""


class LinearAPIError(Exception):
    """Raised when Linear's GraphQL endpoint returns a logical error.

    Distinct from ``httpx.HTTPError`` (transport / HTTP-status failures)
    so callers can catch both failure classes precisely.
    """
