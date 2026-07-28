from typing import Any, Protocol


class CacheStore(Protocol):
    """What the domain needs from a cache — nothing about DynamoDB leaks through."""

    async def get(self, key: str) -> list[dict[str, Any]] | dict[str, Any] | None:
        """Return cached value or None on miss."""
        ...

    async def set(
        self,
        key: str,
        value: list[dict[str, Any]] | dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        """Write value with TTL. Fire-and-forget — domain ignores errors."""
        ...
