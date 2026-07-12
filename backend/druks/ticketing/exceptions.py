class TrackerError(Exception):
    pass


class TrackerNotConfigured(TrackerError):
    def __init__(self, source: str) -> None:
        super().__init__(f"ticketing provider {source!r} is not configured")
        self.source = source
