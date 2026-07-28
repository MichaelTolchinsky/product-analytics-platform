from pathlib import Path

from analytics_platform import BaseServiceSettings

_REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent


class ServingSettings(BaseServiceSettings):
    s3_bucket: str = "analytics-lake"
    athena_database: str = "analytics"
    athena_output: str = "s3://analytics-lake/athena-results/"

    # v2: Redshift Serverless (Data API)
    redshift_workgroup: str = "analytics"
    redshift_database: str = "analytics"

    # v2: DynamoDB cache — disabled locally (Floci DynamoDB state survives volume
    # wipes and causes cross-key corruption; cache adds no latency benefit with DuckDB)
    dynamodb_cache_table: str = "metrics-cache"
    cache_enabled: bool = True  # set CACHE_ENABLED=false to disable

    # dashboard static files — override with DASHBOARD_DIR env var in production
    dashboard_dir: Path = _REPO_ROOT / "dashboard"
