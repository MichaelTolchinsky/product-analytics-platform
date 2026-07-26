from typing import Protocol


class CheckpointStore(Protocol):
    """Persists how far the reader has durably progressed, for crash recovery."""

    async def load(self) -> str | None: ...
    async def save(self, sequence_number: str) -> None: ...
