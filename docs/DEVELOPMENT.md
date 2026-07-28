# Development

Local setup and load testing for the Product Analytics Platform.
For system design, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) — runs Floci + services
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager

No AWS account needed. Everything runs locally against **Floci**, a free
MIT-licensed AWS emulator with a real DuckDB backend for Athena.

## Quickstart

```bash
make up
```

This single command:

1. Starts Floci (local AWS — Kinesis, S3, Glue, Athena, DynamoDB)
2. Creates all AWS resources (stream, bucket, Glue tables, DynamoDB cache)
3. Starts the Ingestion API and Consumer via Docker Compose
4. Sends **5,000 events** through the full pipeline as a smoke test
5. Runs the Athena jobs: bronze → silver → gold
6. Starts the Analytics API

Once complete, the stack is fully live:

| Service | URL |
|---|---|
| Ingestion API | <http://localhost:8000> |
| Analytics API | <http://localhost:8001> |
| API docs (Ingestion) | <http://localhost:8000/docs> |
| API docs (Analytics) | <http://localhost:8001/docs> |
| Dashboard | <http://localhost:8001> |

## Try it

**Send a single event:**

```bash
curl -s -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "test-001",
    "event_type": "page_view",
    "timestamp": "2024-01-15T10:00:00Z",
    "user_id": "user-123",
    "session_id": "sess-abc",
    "page": "/products",
    "metadata": {}
  }' | jq
```

**Query a metric:**

```bash
curl -s http://localhost:8001/metrics/dau | jq
curl -s http://localhost:8001/metrics/top-pages | jq
curl -s http://localhost:8001/metrics/conversion | jq
```

**Run jobs manually** (rebuild silver + gold from current bronze):

```bash
make jobs-local
```

## Load testing

The load generator simulates realistic user sessions — weighted event types
(60% page views, 20% clicks, 10% searches, 5% signups, 5% purchases) across
random users, sessions, and pages.

**Quick run (10k events):**

```bash
TOTAL_EVENTS=10000 CONCURRENCY=500 uv run python -m load_gen.runner
```

**Tunable parameters:**

| Variable | Default | Description |
|---|---|---|
| `TOTAL_EVENTS` | 100,000 | Total events to send |
| `CONCURRENCY` | 200 | Max concurrent in-flight requests |
| `INGESTION_URL` | `http://localhost:8000` | Target ingestion endpoint |

**Output format:**

```
done in 190.9s — sent=10000 accepted=10000 rejected=0 failed=0 rps=52 avg=9292ms p99=10551ms
```

## Other commands

```bash
make down          # stop and remove all containers + volumes
make build         # rebuild Docker images
make test          # run pytest
make lint          # ruff check + format check
make lint-fix      # auto-fix lint issues
make flush-cache   # clear DynamoDB metrics cache (forces fresh Athena queries)
make setup         # install all services in editable mode (for IDE support)
```

