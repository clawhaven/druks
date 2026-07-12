# The in-VM filesystem layout: where credentials, the helper script, and the
# workspace live on a sandbox host, all derived from the SSH user's home so
# non-root users (e.g. ``exedev`` on the standard exuntu image) can ``mkdir``
# and own every subdir.

# In-VM credential destinations, RELATIVE to the agent user's home.
# These must match the exact files the Linux CLIs read on startup —
# getting them wrong silently falls back to unauthenticated (or a
# login prompt that hangs a headless run):
#
#   - Claude Code (Linux) reads its OAuth credentials from the HIDDEN
#     file ``~/.claude/.credentials.json`` (note the leading dot).
#     macOS uses the login Keychain instead, but Druks runs on Linux.
#   - Codex CLI reads ``~/.codex/auth.json`` (NOT ``credentials.json``).
#
# The agent process resolves ``$HOME`` from whichever user SSHes into
# the VM (``SandboxSettings.ssh_username`` / ``DRUKS_SANDBOX_SSH_USERNAME``).
# On the exuntu image that's ``exedev`` (→ /home/exedev), not root, so
# destinations are computed per-user via :func:`get_remote_home` rather
# than hardcoded. The credential content is synthesized from the DB row
# (``Harness.render_credentials_file()``) and written there as a secret.
CLAUDE_CRED_HOME_SUFFIX = ".claude/.credentials.json"
CODEX_AUTH_HOME_SUFFIX = ".codex/auth.json"


def get_remote_home(ssh_username: str) -> str:
    return "/root" if ssh_username == "root" else f"/home/{ssh_username}"


def get_claude_credentials_remote(ssh_username: str) -> str:
    return f"{get_remote_home(ssh_username)}/{CLAUDE_CRED_HOME_SUFFIX}"


def get_codex_auth_remote(ssh_username: str) -> str:
    return f"{get_remote_home(ssh_username)}/{CODEX_AUTH_HOME_SUFFIX}"


def get_helper_script_path(ssh_username: str) -> str:
    # Where the uploaded ``druks-sandbox`` helper script lands.
    return f"{get_remote_home(ssh_username)}/druks-sandbox"


def get_work_root(ssh_username: str) -> str:
    return f"{get_remote_home(ssh_username)}/work"


def get_repo_root(ssh_username: str) -> str:
    return f"{get_work_root(ssh_username)}/repo"


def get_runs_root(ssh_username: str) -> str:
    return f"{get_work_root(ssh_username)}/runs"


def get_related_root(ssh_username: str) -> str:
    return f"{get_work_root(ssh_username)}/related"


def get_github_token_remote_path(ssh_username: str) -> str:
    return f"{get_work_root(ssh_username)}/github-token"
