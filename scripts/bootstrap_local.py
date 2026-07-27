"""scripts/bootstrap_local.py

One-time setup script that creates all AWS resources in Floci before
running the local stack. Idempotent — safe to run multiple times.

Usage:
    python scripts/bootstrap_local.py

Requires Floci to be running:
    docker compose up floci
"""

import asyncio
import io
import logging

import aioboto3
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config — matches docker-compose.yml env vars
# ---------------------------------------------------------------------------

ENDPOINT   = "http://localhost:4566"
REGION     = "eu-north-1"
BUCKET     = "analytics-lake"
STREAM     = "events"
DATABASE   = "analytics"

AWS_CREDS  = {
    "aws_access_key_id":     "test",
    "aws_secret_access_key": "test",
    "region_name":           REGION,
    "endpoint_url":          ENDPOINT,
}

# Partition projection config shared across bronze and silver tables
PARTITION_PROJECTION = {
    "projection.enabled":          "true",
    "projection.year.type":        "integer",
    "projection.year.range":       "2024,2030",
    "projection.month.type":       "integer",
    "projection.month.range":      "1,12",
    "projection.month.digits":     "2",
    "projection.day.type":         "integer",
    "projection.day.range":        "1,31",
    "projection.day.digits":       "2",
    "projection.hour.type":        "integer",
    "projection.hour.range":       "0,23",
    "projection.hour.digits":      "2",
    "storage.location.template":   f"s3://{BUCKET}/bronze/year=${{year}}/month=${{month}}/day=${{day}}/hour=${{hour}}",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def create_kinesis_stream(client) -> None:
    try:
        await client.create_stream(StreamName=STREAM, ShardCount=1)
        logger.info("kinesis stream '%s' created", STREAM)
    except client.exceptions.ResourceInUseException:
        logger.info("kinesis stream '%s' already exists", STREAM)


async def create_s3_bucket(client) -> None:
    try:
        await client.create_bucket(Bucket=BUCKET)
        logger.info("s3 bucket '%s' created", BUCKET)
    except client.exceptions.BucketAlreadyOwnedByYou:
        logger.info("s3 bucket '%s' already exists", BUCKET)


async def create_glue_database(client) -> None:
    try:
        await client.create_database(
            DatabaseInput={"Name": DATABASE, "Description": "Analytics platform data lake"}
        )
        logger.info("glue database '%s' created", DATABASE)
    except client.exceptions.AlreadyExistsException:
        logger.info("glue database '%s' already exists", DATABASE)


async def create_or_update_table(client, table_input: dict) -> None:
    name = table_input["Name"]
    try:
        await client.create_table(DatabaseName=DATABASE, TableInput=table_input)
        logger.info("glue table '%s' created", name)
    except client.exceptions.AlreadyExistsException:
        await client.update_table(DatabaseName=DATABASE, TableInput=table_input)
        logger.info("glue table '%s' updated", name)


# ---------------------------------------------------------------------------
# Table definitions
# ---------------------------------------------------------------------------

def bronze_table() -> dict:
    return {
        "Name": "bronze",
        "Description": "Raw events as ingested — may contain duplicates",
        "StorageDescriptor": {
            "Columns": [
                {"Name": "event_id",   "Type": "string"},
                {"Name": "event_type", "Type": "string"},
                {"Name": "timestamp",  "Type": "string"},
                {"Name": "user_id",    "Type": "string"},
                {"Name": "session_id", "Type": "string"},
                {"Name": "page",       "Type": "string"},
                {"Name": "metadata",   "Type": "string"},
            ],
            "Location":       f"s3://{BUCKET}/bronze/",
            "InputFormat":    "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
            "OutputFormat":   "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
            "SerdeInfo": {
                "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe",
            },
        },
        "PartitionKeys": [
            {"Name": "year",  "Type": "int"},
            {"Name": "month", "Type": "int"},
            {"Name": "day",   "Type": "int"},
            {"Name": "hour",  "Type": "int"},
        ],
        "Parameters": {
            **PARTITION_PROJECTION,
            "storage.location.template": f"s3://{BUCKET}/bronze/year=${{year}}/month=${{month}}/day=${{day}}/hour=${{hour}}",
        },
    }


def silver_table() -> dict:
    return {
        "Name": "silver",
        "Description": "Clean events — deduped, validated, typed timestamps",
        "StorageDescriptor": {
            "Columns": [
                {"Name": "event_id",   "Type": "string"},
                {"Name": "event_type", "Type": "string"},
                {"Name": "timestamp",  "Type": "timestamp"},
                {"Name": "user_id",    "Type": "string"},
                {"Name": "session_id", "Type": "string"},
                {"Name": "page",       "Type": "string"},
                {"Name": "metadata",   "Type": "string"},
            ],
            "Location":       f"s3://{BUCKET}/silver/",
            "InputFormat":    "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
            "OutputFormat":   "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
            "SerdeInfo": {
                "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe",
            },
        },
        "PartitionKeys": [
            {"Name": "year",  "Type": "int"},
            {"Name": "month", "Type": "int"},
            {"Name": "day",   "Type": "int"},
            {"Name": "hour",  "Type": "int"},
        ],
        "Parameters": {
            **PARTITION_PROJECTION,
            "storage.location.template": f"s3://{BUCKET}/silver/year=${{year}}/month=${{month}}/day=${{day}}/hour=${{hour}}",
        },
    }


def gold_table(name: str, columns: list[dict], location_suffix: str) -> dict:
    return {
        "Name": name,
        "Description": f"Precomputed gold metric: {name}",
        "StorageDescriptor": {
            "Columns": columns,
            "Location":     f"s3://{BUCKET}/gold/{location_suffix}/",
            "InputFormat":  "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
            "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
            "SerdeInfo": {
                "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe",
            },
        },
        "PartitionKeys": [],  # gold tables are not partitioned — small, full-scan is cheap
        "Parameters": {"classification": "parquet"},
    }


GOLD_TABLES = [
    gold_table("gold_dau", [
        {"Name": "date", "Type": "date"},
        {"Name": "dau",  "Type": "int"},
    ], "dau"),

    gold_table("gold_top_pages", [
        {"Name": "page",  "Type": "string"},
        {"Name": "views", "Type": "int"},
        {"Name": "rn",    "Type": "int"},
    ], "top_pages"),

    gold_table("gold_events", [
        {"Name": "event_type", "Type": "string"},
        {"Name": "count",      "Type": "int"},
    ], "events"),

    gold_table("gold_conversion", [
        {"Name": "converted_sessions",    "Type": "int"},
        {"Name": "total_signup_sessions", "Type": "int"},
        {"Name": "conversion_rate_pct",   "Type": "double"},
    ], "conversion"),

    gold_table("gold_searches", [
        {"Name": "query", "Type": "string"},
        {"Name": "count", "Type": "int"},
        {"Name": "rn",    "Type": "int"},
    ], "searches"),
]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def seed_gold_tables(s3_client) -> None:
    """Write an empty Parquet file to each table's S3 location.

    Floci's DuckDB backend errors if it can't find any files at a Glue
    table's S3 location — even for queries that don't read that table.
    A zero-row Parquet file satisfies the path check.
    """
    EVENT_SCHEMA = pa.schema([
        ("event_id",   pa.string()),
        ("event_type", pa.string()),
        ("timestamp",  pa.string()),
        ("user_id",    pa.string()),
        ("session_id", pa.string()),
        ("page",       pa.string()),
        ("metadata",   pa.string()),
        ("year",       pa.int32()),
        ("month",      pa.int32()),
        ("day",        pa.int32()),
        ("hour",       pa.int32()),
    ])

    SILVER_SCHEMA = pa.schema([
        ("event_id",   pa.string()),
        ("event_type", pa.string()),
        ("timestamp",  pa.timestamp("us", tz="UTC")),
        ("user_id",    pa.string()),
        ("session_id", pa.string()),
        ("page",       pa.string()),
        ("metadata",   pa.string()),
        ("year",       pa.int32()),
        ("month",      pa.int32()),
        ("day",        pa.int32()),
        ("hour",       pa.int32()),
    ])

    seeds = {
        "bronze/_seed.parquet":          EVENT_SCHEMA,
        "silver/_seed.parquet":          SILVER_SCHEMA,
        "gold/dau/_seed.parquet":        pa.schema([("date", pa.date32()), ("dau", pa.int32())]),
        "gold/top_pages/_seed.parquet":  pa.schema([("page", pa.string()), ("views", pa.int32()), ("rn", pa.int32())]),
        "gold/events/_seed.parquet":     pa.schema([("event_type", pa.string()), ("count", pa.int32())]),
        "gold/conversion/_seed.parquet": pa.schema([("converted_sessions", pa.int32()), ("total_signup_sessions", pa.int32()), ("conversion_rate_pct", pa.float64())]),
        "gold/searches/_seed.parquet":   pa.schema([("query", pa.string()), ("count", pa.int32()), ("rn", pa.int32())]),
    }

    for key, schema in seeds.items():
        table = pa.table({col: [] for col in schema.names}, schema=schema)
        buf = io.BytesIO()
        pq.write_table(table, buf)
        await s3_client.put_object(Bucket=BUCKET, Key=key, Body=buf.getvalue())
        logger.info("seeded s3://%s/%s", BUCKET, key)


async def bootstrap() -> None:
    session = aioboto3.Session()

    async with (
        session.client("kinesis", **AWS_CREDS) as kinesis,
        session.client("s3",      **AWS_CREDS) as s3,
        session.client("glue",    **AWS_CREDS) as glue,
    ):
        await create_kinesis_stream(kinesis)
        await create_s3_bucket(s3)
        await create_glue_database(glue)
        await create_or_update_table(glue, bronze_table())
        await create_or_update_table(glue, silver_table())
        for table in GOLD_TABLES:
            await create_or_update_table(glue, table)
        await seed_gold_tables(s3)

    logger.info("bootstrap complete — local stack is ready")


if __name__ == "__main__":
    asyncio.run(bootstrap())
