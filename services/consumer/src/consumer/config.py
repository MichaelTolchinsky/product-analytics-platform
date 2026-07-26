from analytics_platform import BaseServiceSettings


class ConsumerSettings(BaseServiceSettings):
    kinesis_stream_name: str = "events"
    s3_bucket: str = "analytics-lake"
    batch_max_size: int = 500
    batch_max_interval_seconds: float = 10.0
    poll_interval_seconds: float = 1.0
