from pathlib import Path
from string import Template
from typing import Any

from analytics_api.contracts.query_engine import QueryEngine

QUERIES_DIR = Path(__file__).parent.parent / "queries"


def _load(name: str, **params: Any) -> str:
    sql = (QUERIES_DIR / f"{name}.sql").read_text()
    return Template(sql).substitute(**params) if params else sql


class AnalyticsService:
    """Ad-hoc analytics queries that scan silver directly via Athena.

    Separate from MetricsService (Redshift gold marts) — different engine,
    different latency profile, different use case (trend/exploration vs KPI).
    """

    def __init__(self, engine: QueryEngine) -> None:
        self._engine = engine

    async def get_dau_trend(self, days: int = 7) -> list[dict[str, Any]]:
        """DAU per day for the last N days. Scans silver by date range."""
        return await self._engine.run(_load("dau_trend", days=days))

    async def get_hourly_events(self) -> list[dict[str, Any]]:
        """Event count by hour for today. Partition-pruned silver scan."""
        return await self._engine.run(_load("hourly_events"))
