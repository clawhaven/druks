import pytest
from druks.signals import publish, subscribe


@pytest.mark.asyncio
async def test_subscriber_failure_propagates_to_the_publisher():
    # The webhook dedup release and the DBOS lifecycle-step retry both rely on
    # publish failing loudly; a swallowed subscriber error would silently lose
    # the event (the provider's redelivery would short-circuit as a duplicate).
    @subscribe("test.subscriber_failure")
    async def boom(**_: object) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await publish("test.subscriber_failure")
