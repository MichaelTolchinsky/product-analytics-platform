from pydantic import BaseModel


class EventAccepted(BaseModel):
    event_id: str
    status: str = "accepted"
