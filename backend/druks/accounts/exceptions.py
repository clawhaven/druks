class InvalidPatError(Exception):
    """A presented bearer credential that resolves to no live personal access
    token — unknown, mismatched, revoked, or expired."""
