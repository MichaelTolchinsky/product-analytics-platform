from analytics_platform import BaseServiceSettings


class LoadGenSettings(BaseServiceSettings):
    ingestion_url: str = "http://localhost:8000"
    total_events: int = 100_000
    concurrency: int = 50        # concurrent workers sending events
    events_per_session: int = 10  # events per simulated user session
