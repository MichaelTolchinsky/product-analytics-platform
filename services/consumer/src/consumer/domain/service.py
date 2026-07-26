import asyncio

from consumer.contracts.lake import LakeWriter
from consumer.contracts.stream import StreamReader
from consumer.domain.batcher import EventBatcher


class ConsumerService:
    """Polls the stream, batches events, flushes to the lake. No AWS imports."""

    def __init__(
        self,
        reader: StreamReader,
        writer: LakeWriter,
        batcher: EventBatcher,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._batcher = batcher
        self._poll_interval_seconds = poll_interval_seconds

    async def run_forever(self) -> None:
        while True:
            await self.poll_once()
            await asyncio.sleep(self._poll_interval_seconds)

    async def poll_once(self) -> None:
        events = await self._reader.read_batch()
        for event in events:
            self._batcher.add(event)

        if not self._batcher.is_ready():
            return

        groups = self._batcher.flush()
        for partition, batch_events in groups.items():
            await self._writer.write_partition(batch_events, partition)

        # only checkpoint after every group has been durably written —
        # on crash mid-flush, we resume before this point and re-write
        # (bronze absorbs duplicates; silver dedupes).
        await self._reader.commit()
