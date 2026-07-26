from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Common settings every service shares.

    Individual services subclass this and add their own fields
    (stream name, bucket name, etc).
    """

    model_config = SettingsConfigDict(extra="ignore")

    env: str = "local"
    aws_region: str = "eu-north-1"
    aws_endpoint_url: str | None = None
    log_level: str = "INFO"
