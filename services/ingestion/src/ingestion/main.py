from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aioboto3
from fastapi import FastAPI

from ingestion.api.routes import router
from ingestion.config import IngestionSettings
from ingestion.domain.service import IngestionService
from ingestion.implementation.kinesis import KinesisPublisher


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = IngestionSettings()
    session = aioboto3.Session()

    async with session.client(
        "kinesis",
        region_name=settings.aws_region,
        endpoint_url=settings.aws_endpoint_url,
    ) as kinesis_client:
        publisher = KinesisPublisher(
            client=kinesis_client,
            stream_name=settings.kinesis_stream_name,
        )
        app.state.ingestion_service = IngestionService(publisher=publisher)
        yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Ingestion API",
        description="Accepts and validates product events, publishes them to the stream.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()
