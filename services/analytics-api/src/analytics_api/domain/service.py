import logging
from pathlib import Path
from string import Template
from typing import Any

from analytics_api.contracts.cache import CacheStore
from analytics_api.contracts.query_engine import QueryEngine

logger = logging.getLogger(__name__)

QUERIES_DIR = Path(__file__).parent.parent / "queries"

# TTL per metric (seconds).  DAU + conversion refresh hourly; others every minute.
_TTL: dict[str, int] = {
    "dau": 300,
    "conversion": 300,
    "top_pages": 60,
    "events": 60,
    "searches": 60,
}


def _load(name: str, **params: Any) -> str:
    """Load a SQL file and substitute any $placeholders with params."""
    sql = (QUERIES_DIR / f"{name}.sql").read_text()
    return Template(sql).substitute(**params) if params else sql


def _cache_key(metric: str, **params: Any) -> str:
    """Stable cache key: metric name + sorted param pairs."""
    if not params:
        return metric
    parts = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return f"{metric}?{parts}"


class MetricsService:
    """Serves analytics metrics by querying precomputed gold tables.
    Knows nothing about Athena, DuckDB, Redshift, or DynamoDB — only the contracts.

    cache is optional: when None, every request goes straight to the engine.
    """

    def __init__(self, engine: QueryEngine, cache: CacheStore | None = None) -> None:
        self._engine = engine
        self._cache = cache

    async def _fetch(
        self,
        metric: str,
        sql: str,
        **key_params: Any,
    ) -> list[dict[str, Any]]:
        """Cache-aside helper: hit → return; miss → query → write → return."""
        if self._cache is None:
            return await self._engine.run(sql)

        key = _cache_key(metric, **key_params)
        cached = await self._cache.get(key)
        if cached is not None:
            return cached if isinstance(cached, list) else [cached]

        rows = await self._engine.run(sql)
        if rows:  # never cache empty results — let next request retry the engine
            try:
                await self._cache.set(key, rows, ttl_seconds=_TTL.get(metric, 60))
            except Exception:
                logger.warning("cache write failed for %s — continuing without cache", key)
        return rows

    async def get_dau(self) -> dict[str, Any]:
        rows = await self._fetch("dau", _load("dau"))
        return rows[0] if rows else {"date": None, "dau": 0}

    async def get_top_pages(self, limit: int = 10) -> list[dict[str, Any]]:
        return await self._fetch("top_pages", _load("top_pages", limit=limit), limit=limit)

    async def get_events(self) -> list[dict[str, Any]]:
        return await self._fetch("events", _load("events"))

    async def get_conversion(self) -> dict[str, Any]:
        rows = await self._fetch("conversion", _load("conversion"))
        return rows[0] if rows else {
            "converted_sessions": 0,
            "total_signup_sessions": 0,
            "conversion_rate_pct": None,
        }

    async def get_searches(self, limit: int = 10) -> list[dict[str, Any]]:
        return await self._fetch("searches", _load("searches", limit=limit), limit=limit)
