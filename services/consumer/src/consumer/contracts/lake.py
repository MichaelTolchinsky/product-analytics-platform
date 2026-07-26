from typing import Protocol

from analytics_platform import Event


class LakeWriter(Protocol):
    """What the domain needs to persist events — nothing about S3/Parquet leaks through."""

    async def write_partition(self, events: list[Event], partition: str) -> None: ...
