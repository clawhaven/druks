from druks.harnesses.models import HarnessConnection
from druks.harnesses.registry import get_harnesses
from druks.workflows import Workflow


class PollUsage(Workflow):
    every = "*/5 * * * *"

    async def run(self) -> dict[str, list[dict[str, object]]]:
        # One scrape per connection — every account's remaining quota is its
        # own row, keyed (harness, account).
        by_name = {harness.name: harness for harness in get_harnesses()}
        connections = [c for c in HarnessConnection.list_all() if c.harness in by_name]
        return {"results": [await by_name[c.harness].poll_usage(c) for c in connections]}
