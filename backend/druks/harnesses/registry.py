from .base import Harness


def get_harnesses() -> tuple[type[Harness], ...]:
    """The registry: every ``Harness`` subclass, sorted by name for a stable
    order. The harness modules are imported in this package's ``__init__`` so
    the subclasses are enrolled."""
    return tuple(sorted(Harness.__subclasses__(), key=lambda harness: harness.name))


def get_harness_for_model(model: str) -> type[Harness]:
    """The harness class that runs ``model``."""
    for harness in get_harnesses():
        if model in harness.models:
            return harness
    # Models are registry-validated on write (allowed_models is the union), so a
    # miss is a real bug — a stale override or a model dropped from a harness —
    # not something to paper over by silently running it on the wrong CLI.
    raise ValueError(f"no registered harness handles model {model!r}")


def allowed_models() -> tuple[str, ...]:
    return tuple(model for harness in get_harnesses() for model in harness.models)
