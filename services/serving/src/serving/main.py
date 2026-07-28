from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aioboto3
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from serving.api.analytics_routes import router as analytics_router
from serving.api.routes import router as metrics_router
from serving.config import ServingSettings
from serving.domain.analytics_service import AnalyticsService
from serving.domain.service import MetricsService
from serving.implementation.athena import AthenaEngine
from serving.implementation.dynamodb_cache import DynamoDBCache
from serving.implementation.duckdb import DuckDBEngine
from serving.implementation.redshift import RedshiftEngine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = ServingSettings()
    session = aioboto3.Session()

    if settings.env == "local":
        # Local: single DuckDB engine for both services.
        # MetricsService uses gold views (Redshift path locally).
        # AnalyticsService uses silver view (Athena path locally).
        endpoint = (settings.aws_endpoint_url or "http://localhost:4566").replace("http://", "")
        engine = DuckDBEngine(
            s3_endpoint=endpoint,
            s3_bucket=settings.s3_bucket,
            s3_region=settings.aws_region,
        )
        app.state.metrics_service   = MetricsService(engine=engine, cache=None)
        app.state.analytics_service = AnalyticsService(engine=engine)
        yield
    else:
        # Production:
        #   MetricsService  → Redshift Serverless (pre-computed gold marts, fast KPIs)
        #   AnalyticsService → Athena (ad-hoc silver scans, trends, exploration)
        async with (
            session.client("redshift-data", region_name=settings.aws_region) as rs_client,
            session.client("dynamodb",      region_name=settings.aws_region) as ddb_client,
            session.client(
                "athena",
                region_name=settings.aws_region,
                endpoint_url=settings.aws_endpoint_url,
            ) as athena_client,
        ):
            redshift_engine = RedshiftEngine(
                client=rs_client,
                workgroup=settings.redshift_workgroup,
                database=settings.redshift_database,
            )
            athena_engine = AthenaEngine(
                client=athena_client,
                database=settings.athena_database,
                output_location=settings.athena_output,
            )
            cache = DynamoDBCache(
                client=ddb_client,
                table_name=settings.dynamodb_cache_table,
            )
            app.state.metrics_service   = MetricsService(engine=redshift_engine, cache=cache)
            app.state.analytics_service = AnalyticsService(engine=athena_engine)
            yield


def create_app() -> FastAPI:
    settings = ServingSettings()
    app = FastAPI(
        title="Serving API",
        description=(
            "Two-tier analytics API: "
            "Redshift (pre-computed KPIs via /metrics) + "
            "Athena (ad-hoc silver scans via /analytics)"
        ),
        version="2.1.0",
        lifespan=lifespan,
    )
    app.include_router(metrics_router)
    app.include_router(analytics_router)
    app.mount("/static", StaticFiles(directory=settings.dashboard_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def dashboard() -> FileResponse:
        return FileResponse(settings.dashboard_dir / "index.html")

    return app


app = create_app()
