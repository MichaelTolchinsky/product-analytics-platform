from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aioboto3
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from serving.api.routes import router
from serving.config import ServingSettings
from serving.domain.service import MetricsService
from serving.implementation.dynamodb_cache import DynamoDBCache
from serving.implementation.duckdb import DuckDBEngine
from serving.implementation.redshift import RedshiftEngine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = ServingSettings()
    session = aioboto3.Session()

    if settings.env == "local":
        # Local: DuckDB reads Parquet from Floci S3; DynamoDB cache via Floci
        endpoint = (settings.aws_endpoint_url or "http://localhost:4566").replace("http://", "")
        engine = DuckDBEngine(
            s3_endpoint=endpoint,
            s3_bucket=settings.s3_bucket,
            s3_region=settings.aws_region,
        )
        async with session.client(
            "dynamodb",
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url or "http://localhost:4566",
        ) as ddb_client:
            cache = DynamoDBCache(
                client=ddb_client,
                table_name=settings.dynamodb_cache_table,
            )
            app.state.metrics_service = MetricsService(engine=engine, cache=cache)
            yield
    else:
        # Production: Redshift Serverless (Data API) + DynamoDB cache
        async with (
            session.client(
                "redshift-data",
                region_name=settings.aws_region,
            ) as rs_client,
            session.client(
                "dynamodb",
                region_name=settings.aws_region,
            ) as ddb_client,
        ):
            engine = RedshiftEngine(
                client=rs_client,
                workgroup=settings.redshift_workgroup,
                database=settings.redshift_database,
            )
            cache = DynamoDBCache(
                client=ddb_client,
                table_name=settings.dynamodb_cache_table,
            )
            app.state.metrics_service = MetricsService(engine=engine, cache=cache)
            yield


def create_app() -> FastAPI:
    settings = ServingSettings()
    app = FastAPI(
        title="Serving API",
        description="Serves precomputed analytics metrics from the gold layer of the data lake.",
        version="2.0.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=settings.dashboard_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def dashboard() -> FileResponse:
        return FileResponse(settings.dashboard_dir / "index.html")

    return app


app = create_app()
