from analytics_platform import BaseServiceSettings


class IngestionSettings(BaseServiceSettings):
    kinesis_stream_name: str = "events"
