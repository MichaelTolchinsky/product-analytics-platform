from typing import Any

import duckdb

GOLD_METRICS = ["dau", "top_pages", "events", "conversion", "searches"]


class DuckDBEngine:
    """QueryEngine backed by DuckDB — reads Parquet files directly from local S3.

    Used locally against Floci: DuckDB can read Parquet files from S3-compatible
    endpoints via its httpfs extension, so the same gold SQL queries that run
    on Athena work on DuckDB with zero changes.
    """

    def __init__(self, s3_endpoint: str, s3_bucket: str, s3_region: str = "eu-north-1") -> None:
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
        # register gold tables as views over S3 Parquet
        for metric in GOLD_METRICS:
            self._conn.execute(f"""
                CREATE OR REPLACE VIEW gold_{metric} AS
                SELECT * FROM read_parquet(
                    's3://{s3_bucket}/gold/{metric}/data.parquet'
                );
            """)
        self._bucket = s3_bucket

    async def run(self, sql: str) -> list[dict[str, Any]]:
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._run_sync, sql)

    def _run_sync(self, sql: str) -> list[dict[str, Any]]:
        result = self._conn.execute(sql)
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]
