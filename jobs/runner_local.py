"""jobs/runner_local.py

Local-only runner that executes silver/gold SQL jobs using DuckDB directly
against Floci S3 — bypasses Athena entirely.

Athena does not support INSERT INTO via Floci's DuckDB COPY wrapper.
This runner reads/writes Parquet via DuckDB's httpfs extension, using
the same SQL files as the production runner — with the following differences:
  - INSERT INTO <table> -> SELECT portion extracted, written via DuckDB COPY
  - table names resolved to S3 paths via hive_partitioning views
  - S3 partitions deleted before write (same idempotency guarantee)

Usage:
    python jobs/runner_local.py

Requires Floci running with Docker socket mounted.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aioboto3
import duckdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

JOBS_DIR = Path(__file__).parent
BUCKET   = "analytics-lake"
ENDPOINT = "localhost:4566"
REGION   = "eu-north-1"

AWS_CREDS = {
    "aws_access_key_id":     "test",
    "aws_secret_access_key": "test",
    "region_name":           REGION,
    "endpoint_url":          f"http://{ENDPOINT}",
}


# ---------------------------------------------------------------------------
# DuckDB setup
# ---------------------------------------------------------------------------

def make_duckdb() -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection wired to Floci S3."""
    conn = duckdb.connect()
    conn.execute(f"""
        INSTALL httpfs;
        LOAD httpfs;
        SET s3_endpoint='{ENDPOINT}';
        SET s3_use_ssl=false;
        SET s3_url_style='path';
        SET s3_access_key_id='test';
        SET s3_secret_access_key='test';
        SET s3_region='{REGION}';
    """)
    return conn


def register_views(conn: duckdb.DuckDBPyConnection) -> None:
    """Register bronze as a DuckDB view over S3 Parquet.

    Uses year=* glob prefix to skip _seed.parquet files at the layer root.
    Silver view is registered after run_silver writes data.
    """
    conn.execute(f"""
        CREATE OR REPLACE VIEW bronze AS
        SELECT * FROM read_parquet('s3://{BUCKET}/bronze/year=*/**/*.parquet',
            hive_partitioning=true);
    """)
    logger.info("registered bronze as DuckDB view")


# ---------------------------------------------------------------------------
# Partition helpers
# ---------------------------------------------------------------------------

def lookback_partitions(hours: int = 3) -> list[dict]:
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return [
        {
            "year":  (now - timedelta(hours=i)).year,
            "month": (now - timedelta(hours=i)).month,
            "day":   (now - timedelta(hours=i)).day,
            "hour":  (now - timedelta(hours=i)).hour,
        }
        for i in range(hours)
    ]


async def delete_prefix(s3_client, prefix: str) -> None:
    """Delete all objects under an S3 prefix."""
    paginator = s3_client.get_paginator("list_objects_v2")
    to_delete = []
    async for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            to_delete.append({"Key": obj["Key"]})
    if not to_delete:
        return
    await s3_client.delete_objects(Bucket=BUCKET, Delete={"Objects": to_delete})
    logger.info("deleted %d objects under %s", len(to_delete), prefix)


# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------

def extract_select(sql: str) -> str:
    """Strip INSERT INTO <table> preamble — return the SELECT portion only."""
    lines = sql.splitlines()
    select_lines = []
    in_select = False
    for line in lines:
        if not in_select and line.strip().upper().startswith("SELECT"):
            in_select = True
        if in_select:
            select_lines.append(line)
    return "\n".join(select_lines)


# ---------------------------------------------------------------------------
# Job runners
# ---------------------------------------------------------------------------

async def run_silver(conn: duckdb.DuckDBPyConnection, s3_client) -> None:
    """Delete target silver partitions then run refine.sql via DuckDB."""
    partitions = lookback_partitions(hours=3)
    for partition in partitions:
        prefix = (
            f"silver/"
            f"year={partition['year']:04d}/"
            f"month={partition['month']:02d}/"
            f"day={partition['day']:02d}/"
            f"hour={partition['hour']:02d}/"
        )
        await delete_prefix(s3_client, prefix)

    sql = (JOBS_DIR / "silver" / "refine.sql").read_text()
    select_sql = extract_select(sql)

    # DuckDB hive partitioned write — writes year=/month=/day=/hour= subfolders
    copy_sql = f"""
        COPY ({select_sql})
        TO 's3://{BUCKET}/silver/'
        (FORMAT PARQUET, PARTITION_BY (year, month, day, hour), OVERWRITE_OR_IGNORE)
    """
    conn.execute(copy_sql)

    count = conn.execute(
        f"SELECT COUNT(*) FROM read_parquet('s3://{BUCKET}/silver/year=*/**/*.parquet', hive_partitioning=true)"
    ).fetchone()[0]
    logger.info("silver/refine done — %d rows in silver", count)

    # refresh silver view so gold jobs see updated data
    conn.execute(f"""
        CREATE OR REPLACE VIEW silver AS
        SELECT * FROM read_parquet('s3://{BUCKET}/silver/year=*/**/*.parquet',
            hive_partitioning=true);
    """)


async def run_gold(conn: duckdb.DuckDBPyConnection, s3_client) -> None:
    """Delete target gold files then run each gold SQL job via DuckDB."""
    gold_jobs = sorted((JOBS_DIR / "gold").glob("*.sql"))

    for sql_file in gold_jobs:
        metric = sql_file.stem
        logger.info("running gold/%s.sql", metric)

        await delete_prefix(s3_client, f"gold/{metric}/")

        sql = sql_file.read_text()
        select_sql = extract_select(sql)
        output = f"s3://{BUCKET}/gold/{metric}/data.parquet"

        conn.execute(f"COPY ({select_sql}) TO '{output}' (FORMAT PARQUET)")
        count = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{output}')").fetchone()[0]
        logger.info("gold/%s done — %d rows", metric, count)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def run() -> None:
    conn = make_duckdb()
    register_views(conn)

    session = aioboto3.Session()
    async with session.client("s3", **AWS_CREDS) as s3_client:
        await run_silver(conn, s3_client)
        await run_gold(conn, s3_client)

    logger.info("all jobs complete")


if __name__ == "__main__":
    asyncio.run(run())
