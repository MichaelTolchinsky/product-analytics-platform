from typing import Annotated, Any

from analytics_platform import EventValidationError
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from ingestion.api.schemas import EventAccepted
from ingestion.domain.service import IngestionService

router = APIRouter(tags=["Events"])


def get_ingestion_service(request: Request) -> IngestionService:
    return request.app.state.ingestion_service


@router.post(
    "/events",
    response_model=EventAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest an event",
    description="Validates and publishes a single product event to the stream. Returns 202 if accepted, 400 if the payload fails schema validation.",
)
async def ingest_event(
    raw: Annotated[dict[str, Any], Body()],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> EventAccepted:
    try:
        event = await service.accept_event(raw)
    except EventValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.errors) from exc

    return EventAccepted(event_id=event.event_id)
