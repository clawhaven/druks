from druks.extensions import Extension


class Core(Extension):
    """The platform's home extension: the webhook providers and the platform
    chores (token refresh, stale-call and sandbox-host reaping) — the package
    walk discovers them like any extension's capabilities."""

    name = "core"
    icon = "hexagon"
    description = "The platform's own capabilities — chores and webhooks."
    builtin = True
