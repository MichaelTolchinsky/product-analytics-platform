from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aioboto3
from fastapi import FastAPI

from serving.api.routes import router
from serving.config import ServingSettings
from serving.domain.service import MetricsService
from serving.implementation.athena import AthenaEngine
from serving.implementation.duckdb import DuckDBEngine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = ServingSettings()

    if settings.env == "local":
        # Local: DuckDB reads Parquet directly from Floci's S3
        # strip http:// prefix — DuckDB httpfs takes host:port only
        endpoint = (settings.aws_endpoint_url or "http://localhost:4566").replace("http://", "")
        engine = DuckDBEngine(
            s3_endpoint=endpoint,
            s3_bucket=settings.s3_bucket,
            s3_region=settings.aws_region,
        )
        app.state.metrics_service = MetricsService(engine=engine)
        yield
    else:
        # Production: Athena queries gold tables via real AWS
        session = aioboto3.Session()
        async with session.client(
            "athena",
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url,
        ) as athena_client:
            engine = AthenaEngine(
                client=athena_client,
                database=settings.athena_database,
                output_location=settings.athena_output,
            )
            app.state.metrics_service = MetricsService(engine=engine)
            yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Serving API",
        description="Serves precomputed analytics metrics from the gold layer of the data lake.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()
