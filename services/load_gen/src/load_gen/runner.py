"""Load generator runner — async concurrent event sender.

Simulates realistic user sessions against the ingestion API.
Tracks throughput, latency, and rejection stats.

Usage:
    python -m load_gen.runner
    TOTAL_EVENTS=1000000 CONCURRENCY=100 python -m load_gen.runner
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field

import httpx

from load_gen.config import LoadGenSettings
from load_gen.generator import make_event, make_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class Stats:
    sent: int = 0
    accepted: int = 0
    rejected: int = 0
    failed: int = 0
    latencies: list[float] = field(default_factory=list)

    def record(self, status: int, latency: float) -> None:
        self.sent += 1
        self.latencies.append(latency)
        if status == 202:
            self.accepted += 1
        elif status == 400:
            self.rejected += 1
        else:
            self.failed += 1

    def summary(self, elapsed: float) -> str:
        avg_ms = (sum(self.latencies) / len(self.latencies) * 1000) if self.latencies else 0
        p99_ms = sorted(self.latencies)[int(len(self.latencies) * 0.99)] * 1000 if self.latencies else 0
        rps = self.sent / elapsed if elapsed > 0 else 0
        return (
            f"sent={self.sent} accepted={self.accepted} "
            f"rejected={self.rejected} failed={self.failed} "
            f"rps={rps:.0f} avg={avg_ms:.1f}ms p99={p99_ms:.1f}ms"
        )


async def send_event(
    client: httpx.AsyncClient,
    url: str,
    stats: Stats,
    semaphore: asyncio.Semaphore,
) -> None:
    """Send one event, record result in stats."""
    user_id, session_id = make_session()
    event = make_event(user_id, session_id)
    payload = event.model_dump(mode="json")

    async with semaphore:
        start = time.monotonic()
        try:
            response = await client.post(url, json=payload)
            stats.record(response.status_code, time.monotonic() - start)
        except httpx.RequestError as exc:
            stats.failed += 1
            logger.warning("request error: %s", exc)


async def run_session(
    client: httpx.AsyncClient,
    url: str,
    stats: Stats,
    semaphore: asyncio.Semaphore,
    events_per_session: int,
) -> None:
    """Send a sequence of events for one simulated user session."""
    user_id, session_id = make_session()

    for _ in range(events_per_session):
        event = make_event(user_id, session_id)
        payload = event.model_dump(mode="json")

        async with semaphore:
            start = time.monotonic()
            try:
                response = await client.post(url, json=payload)
                stats.record(response.status_code, time.monotonic() - start)
            except httpx.RequestError as exc:
                stats.failed += 1
                logger.warning("request error: %s", exc)


async def run() -> None:
    settings = LoadGenSettings()
    url = f"{settings.ingestion_url}/events"
    semaphore = asyncio.Semaphore(settings.concurrency)
    stats = Stats()

    sessions = settings.total_events // settings.events_per_session

    logger.info(
        "starting load test: %d events across %d sessions, concurrency=%d → %s",
        settings.total_events, sessions, settings.concurrency, url,
    )

    start = time.monotonic()

    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = [
            run_session(client, url, stats, semaphore, settings.events_per_session)
            for _ in range(sessions)
        ]
        await asyncio.gather(*tasks)

    elapsed = time.monotonic() - start
    logger.info("done in %.1fs — %s", elapsed, stats.summary(elapsed))


if __name__ == "__main__":
    asyncio.run(run())
