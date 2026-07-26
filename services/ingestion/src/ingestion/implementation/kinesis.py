from typing import Any

from analytics_platform import Event


class KinesisPublisher:
    """Real StreamPublisher, backed by Kinesis (or Floci locally).

    Takes an already-open aioboto3 Kinesis client rather than creating one
    per call — the client is a connection pool, and this service is meant
    to sustain high throughput under load testing.
    """

    def __init__(self, client: Any, stream_name: str) -> None:
        self._client = client
        self._stream_name = stream_name

    async def publish(self, event: Event) -> None:
        await self._client.put_record(
            StreamName=self._stream_name,
            Data=event.model_dump_json().encode("utf-8"),
            PartitionKey=event.session_id,
        )
