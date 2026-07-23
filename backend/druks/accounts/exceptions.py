class InvalidPatError(Exception):
    """A presented bearer credential that resolves to no live personal access
    token — unknown, mismatched, revoked, or expired."""


class AuthConfigurationError(Exception):
    """The configured auth mode cannot resolve a single operator identity —
    e.g. ``none`` mode with more than one non-system account. Refuses the
    request (and startup) instead of guessing which account is the operator."""
