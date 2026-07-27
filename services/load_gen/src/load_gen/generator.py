"""Event generator — pure logic, no I/O, no randomness from system state.

Generates realistic product events with configurable sessions and pages.
"""

import random
import uuid
from datetime import UTC, datetime

from analytics_platform import Event, EventType

PAGES = [
    "/home",
    "/products",
    "/products/shoes",
    "/products/jackets",
    "/search",
    "/cart",
    "/checkout",
    "/account",
    "/about",
]

SEARCH_QUERIES = [
    "shoes",
    "blue jacket",
    "running shoes",
    "winter coat",
    "sneakers",
    "leather bag",
    "sunglasses",
    "hoodie",
]

# Weighted distribution matching realistic product analytics traffic
EVENT_WEIGHTS = {
    EventType.PAGE_VIEW:    60,
    EventType.BUTTON_CLICK: 20,
    EventType.SEARCH:       10,
    EventType.SIGNUP:        5,
    EventType.PURCHASE:      5,
}


def make_event(user_id: str, session_id: str) -> Event:
    """Generate one realistic event for a given user/session."""
    event_type = random.choices(
        list(EVENT_WEIGHTS.keys()),
        weights=list(EVENT_WEIGHTS.values()),
        k=1,
    )[0]

    metadata: dict = {}
    if event_type == EventType.SEARCH:
        metadata = {"query": random.choice(SEARCH_QUERIES)}
    elif event_type == EventType.PURCHASE:
        metadata = {"amount": round(random.uniform(9.99, 299.99), 2)}
    elif event_type == EventType.BUTTON_CLICK:
        metadata = {"button": random.choice(["add_to_cart", "buy_now", "wishlist"])}

    return Event(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        timestamp=datetime.now(UTC),
        user_id=user_id,
        session_id=session_id,
        page=random.choice(PAGES),
        metadata=metadata,
    )


def make_session() -> tuple[str, str]:
    """Return a fresh (user_id, session_id) pair."""
    return str(uuid.uuid4()), str(uuid.uuid4())
