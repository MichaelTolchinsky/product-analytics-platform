from typing import Annotated

from fastapi import APIRouter, Depends, Request

from serving.api.schemas import DAUTrendResponse, HourlyEventsResponse
from serving.domain.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def get_analytics_service(request: Request) -> AnalyticsService:
    return request.app.state.analytics_service


@router.get(
    "/dau-trend",
    response_model=DAUTrendResponse,
    summary="DAU trend — Athena scan over silver",
)
async def get_dau_trend(
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    days: int = 7,
) -> DAUTrendResponse:
    rows = await service.get_dau_trend(days=days)
    return DAUTrendResponse(days=days, trend=[
        {"date": r["date"], "dau": int(r["dau"])} for r in rows
    ])


@router.get(
    "/hourly-events",
    response_model=HourlyEventsResponse,
    summary="Hourly event volume today — Athena scan over silver",
)
async def get_hourly_events(
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> HourlyEventsResponse:
    rows = await service.get_hourly_events()
    return HourlyEventsResponse(events=[
        {"hour": int(r["hour"]), "count": int(r["count"])} for r in rows
    ])
