from datetime import date

from pydantic import BaseModel


class DAUResponse(BaseModel):
    date: date | None
    dau: int


class PageViewItem(BaseModel):
    page: str
    views: int
    rn: int


class TopPagesResponse(BaseModel):
    pages: list[PageViewItem]


class EventCountItem(BaseModel):
    event_type: str
    count: int


class EventsResponse(BaseModel):
    events: list[EventCountItem]


class ConversionResponse(BaseModel):
    converted_sessions: int
    total_signup_sessions: int
    conversion_rate_pct: float | None


class SearchItem(BaseModel):
    query: str
    count: int
    rn: int


class SearchesResponse(BaseModel):
    searches: list[SearchItem]
