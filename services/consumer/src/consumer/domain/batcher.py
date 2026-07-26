import time
from collections import defaultdict

from analytics_platform import Event


class EventBatcher:
    """Accumulates events until a size or time threshold is hit, then groups
    the buffered events by partition for writing. Pure logic — no I/O.
    """

    def __init__(self, max_size: int, max_interval_seconds: float) -> None:
        self._max_size = max_size
        self._max_interval_seconds = max_interval_seconds
        self._events: list[Event] = []
        self._batch_started_at: float | None = None

    def add(self, event: Event) -> None:
        if not self._events:
            self._batch_started_at = time.monotonic()
        self._events.append(event)

    def is_ready(self) -> bool:
        if not self._events:
            return False
        if len(self._events) >= self._max_size:
            return True

        assert self._batch_started_at is not None
        elapsed = time.monotonic() - self._batch_started_at
        return elapsed >= self._max_interval_seconds

    def flush(self) -> dict[str, list[Event]]:
        """Group buffered events by partition and clear the buffer."""
        groups: dict[str, list[Event]] = defaultdict(list)
        for event in self._events:
            groups[event.partition()].append(event)

        self._events = []
        self._batch_started_at = None
        return dict(groups)
