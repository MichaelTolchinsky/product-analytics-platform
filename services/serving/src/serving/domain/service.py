from pathlib import Path
from string import Template
from typing import Any

from serving.contracts.query_engine import QueryEngine

QUERIES_DIR = Path(__file__).parent.parent / "queries"


def _load(name: str, **params: Any) -> str:
    """Load a SQL file and substitute any $placeholders with params."""
    sql = (QUERIES_DIR / f"{name}.sql").read_text()
    return Template(sql).substitute(**params) if params else sql


class MetricsService:
    """Serves analytics metrics by querying precomputed gold tables.
    Knows nothing about Athena or DuckDB — only the QueryEngine contract.
    """

    def __init__(self, engine: QueryEngine) -> None:
        self._engine = engine

    async def get_dau(self) -> dict[str, Any]:
        rows = await self._engine.run(_load("dau"))
        return rows[0] if rows else {"date": None, "dau": 0}

    async def get_top_pages(self, limit: int = 10) -> list[dict[str, Any]]:
        return await self._engine.run(_load("top_pages", limit=limit))

    async def get_events(self) -> list[dict[str, Any]]:
        return await self._engine.run(_load("events"))

    async def get_conversion(self) -> dict[str, Any]:
        rows = await self._engine.run(_load("conversion"))
        return rows[0] if rows else {
            "converted_sessions": 0,
            "total_signup_sessions": 0,
            "conversion_rate_pct": None,
        }

    async def get_searches(self, limit: int = 10) -> list[dict[str, Any]]:
        return await self._engine.run(_load("searches", limit=limit))
