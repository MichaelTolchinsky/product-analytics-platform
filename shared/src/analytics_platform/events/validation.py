from typing import Any

from pydantic import ValidationError

from analytics_platform.events.models import Event


class EventValidationError(Exception):
    """Raised when a raw payload fails to parse into a valid Event."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        super().__init__(f"Event validation failed: {errors}")


def parse_event(raw: dict[str, Any]) -> Event:
    """Validate and parse a raw payload into an Event.

    Raises EventValidationError (not pydantic's ValidationError) so callers
    across services depend on one exception type, not a pydantic internal.
    """
    try:
        return Event.model_validate(raw)
    except ValidationError as exc:
        raise EventValidationError(exc.errors()) from exc
