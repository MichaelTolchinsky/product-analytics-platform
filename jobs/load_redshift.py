"""jobs/load_redshift.py

Loads precomputed gold Parquet files into Redshift Serverless mart tables.
Runs after each gold job completes (EventBridge chained trigger in production).

Pattern per metric:
  1. TRUNCATE gold_<metric>   — fast, idempotent wipe
  2. COPY gold_<metric> FROM  — bulk load from S3 Parquet

Both statements go through the Redshift Data API (no persistent connection).

Local: skip entirely — DuckDB in the serving API reads gold Parquet directly.

Usage (manual, after runner_local.py):
    python jobs/load_redshift.py   # env=local → exits immediately
    ENV=production python jobs/load_redshift.py
"""

import asyncio
import logging

import aioboto3
from analytics_platform import BaseServiceSettings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MAX_WAIT_SECONDS = 60

METRICS = ["dau", "top_pages", "events", "searches", "conversion"]


class LoadSettings(BaseServiceSettings):
    s3_bucket: str = "analytics-lake"
    redshift_workgroup: str = "analytics"
    redshift_database: str = "analytics"
    redshift_iam_role: str = ""  # ARN; required in production


# ---------------------------------------------------------------------------
# Redshift Data API helpers
# ---------------------------------------------------------------------------

async def _run_statement(client, workgroup: str, database: str, sql: str, label: str) -> None:
    """Submit a single SQL statement, poll until FINISHED, raise on failure."""
    response = await client.execute_statement(
        WorkgroupName=workgroup,
        Database=database,
        Sql=sql,
    )
    statement_id = response["Id"]
    logger.debug("%s → statement_id=%s", label, statement_id)

    loop = asyncio.get_running_loop()
    deadline = loop.time() + MAX_WAIT_SECONDS

    while True:
        if loop.time() > deadline:
            raise TimeoutError(f"{label}: statement {statement_id} exceeded {MAX_WAIT_SECONDS}s")

        status = await client.describe_statement(Id=statement_id)
        state = status["Status"]

        if state == "FINISHED":
            logger.info("%s FINISHED", label)
            return
        if state in {"FAILED", "ABORTED"}:
            error = status.get("Error", "unknown")
            raise RuntimeError(f"{label}: statement {statement_id} {state}: {error}")

        await asyncio.sleep(0.5)


# ---------------------------------------------------------------------------
# Load job
# ---------------------------------------------------------------------------

async def load_metric(
    client,
    metric: str,
    settings: LoadSettings,
) -> None:
    """TRUNCATE + COPY one metric mart table from gold S3 Parquet."""
    table = f"gold_{metric}"
    s3_path = f"s3://{settings.s3_bucket}/gold/{metric}/"

    await _run_statement(
        client,
        settings.redshift_workgroup,
        settings.redshift_database,
        f"TRUNCATE {table};",
        label=f"truncate:{metric}",
    )

    copy_sql = (
        f"COPY {table} "
        f"FROM '{s3_path}' "
        f"IAM_ROLE '{settings.redshift_iam_role}' "
        f"FORMAT AS PARQUET;"
    )
    await _run_statement(
        client,
        settings.redshift_workgroup,
        settings.redshift_database,
        copy_sql,
        label=f"copy:{metric}",
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def run() -> None:
    settings = LoadSettings()

    if settings.env == "local":
        logger.info("local env — skipping Redshift load (serving uses DuckDB directly)")
        return

    if not settings.redshift_iam_role:
        raise ValueError("REDSHIFT_IAM_ROLE must be set in production")

    session = aioboto3.Session()
    async with session.client(
        "redshift-data",
        region_name=settings.aws_region,
    ) as client:
        for metric in METRICS:
            logger.info("loading %s", metric)
            await load_metric(client, metric, settings)

    logger.info("all metrics loaded into Redshift")


if __name__ == "__main__":
    asyncio.run(run())
