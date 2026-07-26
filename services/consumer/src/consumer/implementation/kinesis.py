import json
import logging
from typing import Any

from analytics_platform import Event, EventValidationError, parse_event

from consumer.contracts.checkpoint import CheckpointStore

logger = logging.getLogger(__name__)


class KinesisReader:
    """Reads one shard of a Kinesis stream.

    v1 targets a single-shard stream. Scaling to N shards means running N
    instances of this reader concurrently, one per shard_id — this class's
    iterator/checkpoint handling doesn't change.
    """

    def __init__(
        self,
        client: Any,
        stream_name: str,
        shard_id: str,
        checkpoint: CheckpointStore,
    ) -> None:
        self._client = client
        self._stream_name = stream_name
        self._shard_id = shard_id
        self._checkpoint = checkpoint
        self._shard_iterator: str | None = None
        self._pending_sequence_number: str | None = None

    async def _ensure_iterator(self) -> str:
        if self._shard_iterator is not None:
            return self._shard_iterator

        last_sequence_number = await self._checkpoint.load()
        if last_sequence_number:
            resp = await self._client.get_shard_iterator(
                StreamName=self._stream_name,
                ShardId=self._shard_id,
                ShardIteratorType="AFTER_SEQUENCE_NUMBER",
                StartingSequenceNumber=last_sequence_number,
            )
        else:
            resp = await self._client.get_shard_iterator(
                StreamName=self._stream_name,
                ShardId=self._shard_id,
                ShardIteratorType="TRIM_HORIZON",
            )

        self._shard_iterator = resp["ShardIterator"]
        return self._shard_iterator

    async def read_batch(self, limit: int = 500) -> list[Event]:
        iterator = await self._ensure_iterator()
        resp = await self._client.get_records(ShardIterator=iterator, Limit=limit)
        self._shard_iterator = resp.get("NextShardIterator")

        events: list[Event] = []
        for record in resp.get("Records", []):
            self._pending_sequence_number = record["SequenceNumber"]
            try:
                raw = json.loads(record["Data"])
                events.append(parse_event(raw))
            except (json.JSONDecodeError, EventValidationError) as exc:
                logger.warning("skipping unparseable record %s: %s", record["SequenceNumber"], exc)

        return events

    async def commit(self) -> None:
        if self._pending_sequence_number is not None:
            await self._checkpoint.save(self._pending_sequence_number)
