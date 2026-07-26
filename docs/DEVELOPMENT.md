# Development

Local dev setup, testing, and experiments for the [Product Analytics Platform](../README.md).
For system design, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Tech Stack

- Python
- FastAPI
- PyArrow
- aioboto3
- AWS CDK
- GitHub Actions
- Floci (local AWS emulation)

## Local Development

All v1 (and v2) development runs locally against **Floci** — a free, MIT-licensed
local AWS emulator — to avoid Kinesis/ALB costs until ready to deploy.

| Component | Local replacement |
| --------- | ----------------- |
| Kinesis, S3, Glue, Athena, EventBridge, CloudWatch | **Floci** (`http://localhost:4566`) |
| Ingestion API, Consumer, Serving API | Docker Compose (same images as Fargate) |
| CDK deployment | `cdk deploy` pointed at Floci endpoint |

**Why Floci over LocalStack:** Athena runs via a real DuckDB backend (not a
stub), so `CTAS`/`INSERT OVERWRITE` queries work on free tier — exactly what the
silver and gold jobs use. Fully free, no account or token required, ~24ms startup.

**Zero code changes** between local and real AWS — all boto3/aioboto3 calls route
through `AWS_ENDPOINT_URL=http://localhost:4566` when set; unset = real AWS.

### Commands

```bash
make setup   # install all services locally (editable mode, for IDE support)
make up      # start Floci + all services via Docker Compose
make test    # run pytest across all services
make lint    # ruff check + format check
```

See the [Makefile](../Makefile) for the full command list.

## Load Testing

**Generate:**
- 100k–1M events
- Multiple concurrent users
- Random sessions / pages

**Measure:**
- API throughput
- Stream throughput
- Processing throughput
- End-to-end ingestion latency
- Analytics query latency
- Data scanned

## Experiments

### 1. Partitioned vs Non-partitioned
Measure:
- Data scanned
- Query latency

### 2. Different batch sizes
Measure:
- Number of output files
- Processing throughput
- End-to-end latency
