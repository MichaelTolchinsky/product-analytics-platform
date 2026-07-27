from analytics_platform import BaseServiceSettings


class ServingSettings(BaseServiceSettings):
    s3_bucket: str = "analytics-lake"
    athena_database: str = "analytics"
    athena_output: str = "s3://analytics-lake/athena-results/"
