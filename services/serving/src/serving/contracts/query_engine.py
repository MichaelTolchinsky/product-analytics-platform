from typing import Any, Protocol


class QueryEngine(Protocol):
    """What the domain needs to run a SQL query — nothing about Athena leaks through."""

    async def run(self, sql: str) -> list[dict[str, Any]]: ...
