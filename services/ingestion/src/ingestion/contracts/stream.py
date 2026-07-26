from typing import Protocol

from analytics_platform import Event


class StreamPublisher(Protocol):
    """What the domain needs from a stream — nothing about Kinesis leaks through."""

    async def publish(self, event: Event) -> None: ...
