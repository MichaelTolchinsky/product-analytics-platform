from enum import StrEnum


class EventType(StrEnum):
    PAGE_VIEW = "page_view"
    BUTTON_CLICK = "button_click"
    SEARCH = "search"
    SIGNUP = "signup"
    PURCHASE = "purchase"
