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

    # v2: DynamoDB cache
    dynamodb_cache_table: str = "metrics-cache"

    # dashboard static files — override with DASHBOARD_DIR env var in production
    dashboard_dir: Path = _REPO_ROOT / "dashboard"
