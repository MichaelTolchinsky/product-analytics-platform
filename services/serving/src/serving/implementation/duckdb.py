from typing import Any
import asyncio

import duckdb

GOLD_METRICS = ["dau", "top_pages", "events", "conversion", "searches"]


class DuckDBEngine:
    """QueryEngine backed by DuckDB — reads Parquet files directly from local S3.

    DuckDB connections are not thread-safe. All queries are serialized through
    an asyncio.Lock so concurrent FastAPI requests don't race on the connection.
    """

    def __init__(self, s3_endpoint: str, s3_bucket: str, s3_region: str = "eu-north-1") -> None:
        self._lock = asyncio.Lock()
        self._conn = duckdb.connect()
        self._conn.execute(f"""
            INSTALL httpfs;
            LOAD httpfs;
            SET s3_endpoint='{s3_endpoint}';
            SET s3_use_ssl=false;
            SET s3_url_style='path';
            SET s3_access_key_id='test';
            SET s3_secret_access_key='test';
            SET s3_region='{s3_region}';
        """)
        # Use glob so view registers lazily — no HTTP check at startup.
        for metric in GOLD_METRICS:
            self._conn.execute(f"""
                CREATE OR REPLACE VIEW gold_{metric} AS
                SELECT * FROM read_parquet(
                    's3://{s3_bucket}/gold/{metric}/*.parquet'
                );
            """)

    async def run(self, sql: str) -> list[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        async with self._lock:
            return await loop.run_in_executor(None, self._run_sync, sql)

    def _run_sync(self, sql: str) -> list[dict[str, Any]]:
        result = self._conn.execute(sql)
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]
