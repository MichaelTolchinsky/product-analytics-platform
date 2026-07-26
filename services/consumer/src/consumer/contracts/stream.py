from typing import Protocol

from analytics_platform import Event


class StreamReader(Protocol):
    """What the domain needs to read from a stream — nothing about Kinesis leaks through."""

    async def read_batch(self) -> list[Event]: ...
    async def commit(self) -> None: ...
