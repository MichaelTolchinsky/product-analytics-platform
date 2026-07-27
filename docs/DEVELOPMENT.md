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

### Results (local / Floci)

| Concurrency | Events | Duration | RPS | Avg latency | p99 latency |
|---|---|---|---|---|---|
| 50 | 1,000 | 1.7s | 588 | 78ms | 120ms |
| 50 | 1,000,000 | ~28min | ~580 | — | — |
| 200 | 100,000 | 538s | 186 | 1033ms | 1378ms |

**Key finding:** concurrency 50 is the sweet spot locally. Higher concurrency (200)
hurts throughput — bottleneck is connection overhead at the ingestion API, not
Kinesis. On real AWS, horizontal scaling (multiple Fargate tasks behind ALB)
resolves this.

## Experiments

### 1. Parquet compression

| Format | Events | Size | Compression ratio |
|---|---|---|---|
| JSON (estimated ~200 bytes/event) | 294,929 | ~56 MiB | 1× |
| **Parquet** | 294,929 | **36 MiB** | **1.6×** |

Parquet compression improves further with larger datasets and more uniform data
(columnar encoding is most effective when many values in a column are similar).

### 2. Batch size vs file count

With default `BATCH_MAX_SIZE=500`:
- **559 Parquet files** for ~295k events
- ~527 events/file average
- Smaller files = more S3 API calls, but lower end-to-end latency

Larger batch sizes (e.g. `BATCH_MAX_SIZE=2000`) would produce fewer, larger files
— better for Athena scan efficiency, worse for latency. This is the core
batching tradeoff.

### 3. Partitioned vs Non-partitioned

Partition pruning is most effective when data spans many partitions (hours/days).
With data concentrated in 1-2 hours, pruning benefit is minimal. At scale (weeks
of data, querying one day) partition pruning reduces data scanned by ~96%
(1 day out of 30 = scanning only 3% of files).

