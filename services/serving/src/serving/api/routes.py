from typing import Annotated

from fastapi import APIRouter, Depends, Request

from serving.api.schemas import (
    ConversionResponse,
    DAUResponse,
    EventsResponse,
    SearchesResponse,
    TopPagesResponse,
)
from serving.domain.service import MetricsService

router = APIRouter(prefix="/metrics", tags=["Metrics"])


def get_metrics_service(request: Request) -> MetricsService:
    return request.app.state.metrics_service


@router.get("/dau", response_model=DAUResponse, summary="Daily Active Users")
async def get_dau(
    service: Annotated[MetricsService, Depends(get_metrics_service)],
) -> DAUResponse:
    result = await service.get_dau()
    return DAUResponse(**result)


@router.get("/top-pages", response_model=TopPagesResponse, summary="Top visited pages")
async def get_top_pages(
    service: Annotated[MetricsService, Depends(get_metrics_service)],
    limit: int = 10,
) -> TopPagesResponse:
    rows = await service.get_top_pages(limit=limit)
    return TopPagesResponse(pages=rows)


@router.get("/events", response_model=EventsResponse, summary="Event counts by type")
async def get_events(
    service: Annotated[MetricsService, Depends(get_metrics_service)],
) -> EventsResponse:
    rows = await service.get_events()
    return EventsResponse(events=rows)


@router.get("/conversion", response_model=ConversionResponse, summary="Signup to purchase conversion rate")
async def get_conversion(
    service: Annotated[MetricsService, Depends(get_metrics_service)],
) -> ConversionResponse:
    result = await service.get_conversion()
    return ConversionResponse(**result)


@router.get("/searches", response_model=SearchesResponse, summary="Top search terms")
async def get_searches(
    service: Annotated[MetricsService, Depends(get_metrics_service)],
    limit: int = 10,
) -> SearchesResponse:
    rows = await service.get_searches(limit=limit)
    return SearchesResponse(searches=rows)
