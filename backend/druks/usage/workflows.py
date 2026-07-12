from druks.harnesses.registry import get_harnesses
from druks.workflows import Workflow


class PollUsage(Workflow):
    every = "*/5 * * * *"

    async def run(self) -> dict[str, list[dict[str, object]]]:
        return {"results": [await h.poll_usage() for h in get_harnesses()]}
