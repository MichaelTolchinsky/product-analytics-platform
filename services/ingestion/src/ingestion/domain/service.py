from typing import Any

from analytics_platform import Event, parse_event

from ingestion.contracts.stream import StreamPublisher


class IngestionService:
    """Validate a raw event and publish it. Knows nothing about HTTP or Kinesis."""

    def __init__(self, publisher: StreamPublisher) -> None:
        self._publisher = publisher

    async def accept_event(self, raw: dict[str, Any]) -> Event:
        """Raises EventValidationError if raw doesn't match the event schema."""
        event = parse_event(raw)
        await self._publisher.publish(event)
        return event
