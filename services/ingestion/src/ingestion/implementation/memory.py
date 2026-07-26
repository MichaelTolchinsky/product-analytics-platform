from analytics_platform import Event


class InMemoryPublisher:
    """Test double satisfying StreamPublisher — no network, no Floci, no AWS."""

    def __init__(self) -> None:
        self.published: list[Event] = []

    async def publish(self, event: Event) -> None:
        self.published.append(event)
