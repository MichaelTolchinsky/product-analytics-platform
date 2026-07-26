from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from analytics_platform.events.types import EventType


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    event_type: EventType
    timestamp: datetime
    user_id: str
    session_id: str
    page: str
    metadata: dict[str, Any] = {}

    def partition(self) -> str:
        return (
            f"year={self.timestamp.year:04d}/"
            f"month={self.timestamp.month:02d}/"
            f"day={self.timestamp.day:02d}/"
            f"hour={self.timestamp.hour:02d}"
        )
