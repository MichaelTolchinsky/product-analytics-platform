"""jobs/runner.py

Executes scheduled Athena jobs for the analytics pipeline.

Run order (called by EventBridge → Fargate task or locally via make):
  1. silver: delete target partitions from S3, then run jobs/silver/refine.sql
  2. gold:   delete target partitions from S3, then run each jobs/gold/*.sql

Both jobs are idempotent — deleting first means reruns produce identical
output and never append duplicate rows.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aioboto3
from analytics_platform import BaseServiceSettings

logger = logging.getLogger(__name__)

JOBS_DIR = Path(__file__).parent
MAX_WAIT_SECONDS = 300


class RunnerSettings(BaseServiceSettings):
    s3_bucket: str = "analytics-lake"
    athena_database: str = "analytics"
    athena_output: str = "s3://analytics-lake/athena-results/"


# ---------------------------------------------------------------------------
# Partition helpers
# ---------------------------------------------------------------------------

def lookback_partitions(hours: int = 3) -> list[dict]:
    """Return the last `hours` hour-buckets as partition dicts (UTC)."""
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


def partition_prefix(layer: str, partition: dict) -> str:
    """Build S3 prefix for a given layer and partition.

    e.g. layer="silver", partition={year:2026,month:7,day:26,hour:14}
         → "silver/year=2026/month=07/day=26/hour=14/"
    """
    return (
        f"{layer}/"
        f"year={partition['year']:04d}/"
        f"month={partition['month']:02d}/"
        f"day={partition['day']:02d}/"
        f"hour={partition['hour']:02d}/"
    )


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

async def delete_partition(s3_client, bucket: str, layer: str, partition: dict) -> None:
    """Delete all S3 objects under a layer/partition prefix.

    Called before each INSERT INTO so the write is an overwrite, not an
    append. If the partition doesn't exist yet (first run), this is a no-op.
    """
    prefix = partition_prefix(layer, partition)
    paginator = s3_client.get_paginator("list_objects_v2")
    objects_to_delete = []

    async for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            objects_to_delete.append({"Key": obj["Key"]})

    if not objects_to_delete:
        logger.debug("no objects to delete under s3://%s/%s", bucket, prefix)
        return

    await s3_client.delete_objects(
        Bucket=bucket,
        Delete={"Objects": objects_to_delete},
    )
    logger.info("deleted %d objects from s3://%s/%s", len(objects_to_delete), bucket, prefix)


# ---------------------------------------------------------------------------
# Athena helpers
# ---------------------------------------------------------------------------

async def _poll(athena_client, query_id: str) -> str:
    """Poll Athena until the query reaches a terminal state, return that state."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + MAX_WAIT_SECONDS

    while True:
        if loop.time() > deadline:
            raise TimeoutError(f"Athena query {query_id} exceeded {MAX_WAIT_SECONDS}s")

        status = await athena_client.get_query_execution(QueryExecutionId=query_id)
        state = status["QueryExecution"]["Status"]["State"]

        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return state

        await asyncio.sleep(2)


async def run_athena_query(
    athena_client,
    sql: str,
    database: str,
    output_location: str,
    label: str = "",
) -> None:
    """Submit SQL to Athena, poll until done, raise on failure.

    ClientRequestToken is a deterministic hash of the SQL + current UTC hour.
    If the runner crashes and retries within the same hour, Athena returns the
    existing QueryExecutionId instead of submitting a duplicate query.
    """
    current_hour = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    token = hashlib.sha256(f"{sql}{current_hour}".encode()).hexdigest()[:128]

    response = await athena_client.start_query_execution(
        QueryString=sql,
        ClientRequestToken=token,
        QueryExecutionContext={"Database": database},
        ResultConfiguration={"OutputLocation": output_location},
    )
    query_id = response["QueryExecutionId"]
    logger.info("submitted %s → query_id=%s", label or "query", query_id)

    state = await _poll(athena_client, query_id)

    if state != "SUCCEEDED":
        status = await athena_client.get_query_execution(QueryExecutionId=query_id)
        reason = status["QueryExecution"]["Status"].get("StateChangeReason", "unknown")
        raise RuntimeError(f"Athena query {query_id} {state}: {reason}")

    logger.info("%s SUCCEEDED (query_id=%s)", label or "query", query_id)


# ---------------------------------------------------------------------------
# Job runners
# ---------------------------------------------------------------------------

async def run_silver(s3_client, athena_client, settings: RunnerSettings) -> None:
    """Delete target silver partitions, then run refine.sql."""
    partitions = lookback_partitions(hours=3)

    logger.info("clearing %d silver partition(s) before refine", len(partitions))
    for partition in partitions:
        await delete_partition(s3_client, settings.s3_bucket, "silver", partition)

    sql = (JOBS_DIR / "silver" / "refine.sql").read_text()
    await run_athena_query(
        athena_client, sql,
        database=settings.athena_database,
        output_location=settings.athena_output,
        label="silver/refine",
    )


async def run_gold(s3_client, athena_client, settings: RunnerSettings) -> None:
    """Delete target gold partitions, then run each gold SQL job."""
    partitions = lookback_partitions(hours=3)
    gold_jobs = sorted((JOBS_DIR / "gold").glob("*.sql"))

    for sql_file in gold_jobs:
        metric = sql_file.stem  # e.g. "dau", "top_pages"
        logger.info("running gold/%s.sql", metric)

        for partition in partitions:
            await delete_partition(s3_client, settings.s3_bucket, f"gold/{metric}", partition)

        sql = sql_file.read_text()
        await run_athena_query(
            athena_client, sql,
            database=settings.athena_database,
            output_location=settings.athena_output,
            label=f"gold/{metric}",
        )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = RunnerSettings()
    session = aioboto3.Session()

    async with (
        session.client(
            "s3",
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url,
        ) as s3_client,
        session.client(
            "athena",
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url,
        ) as athena_client,
    ):
        await run_silver(s3_client, athena_client, settings)
        await run_gold(s3_client, athena_client, settings)


if __name__ == "__main__":
    asyncio.run(run())
