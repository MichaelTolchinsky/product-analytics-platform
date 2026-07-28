# Product Analytics Platform

An end-to-end streaming analytics platform: product events flow through
Kinesis, land as partitioned Parquet in a data lake, and get served back as
live analytics. Built to demonstrate core **data engineering** concepts —
streaming ingestion, medallion architecture, columnar storage, partitioning,
and a two-tier serving layer — rather than another CRUD app.

## What it does

```
POST /events  →  Kinesis  →  Consumer  →  S3 (bronze Parquet)
                                              ↓  Athena jobs (hourly)
                                           silver (deduped + typed)
                                              ↓  Athena jobs (hourly)
                                            gold (precomputed metrics)
                                              ↓
GET /metrics/*  ←  DynamoDB cache  ←  Analytics API  →  Athena / Redshift
```

## Scope

Everything in this repo is **fully implemented and runs locally** via Docker
Compose + Floci (a free, MIT-licensed local AWS emulator).

| Layer | What's built |
|---|---|
| **Ingestion** | FastAPI service — validates events, publishes to Kinesis |
| **Consumer** | Long-running service — batches events, writes partitioned Parquet to S3 |
| **Jobs** | Athena SQL — bronze → silver (dedupe, type), silver → gold (DAU, top pages, conversion, searches, event counts) |
| **Analytics API** | FastAPI service — serves gold metrics; DynamoDB cache-aside; Athena or Redshift engine swappable via one line |
| **Load generator** | Async Python — simulates realistic user sessions, reports RPS + latency |
| **Infra (CDK)** | 6 stacks: VPC, S3/Kinesis/Glue/Athena, Redshift Serverless + DynamoDB, ECS Fargate + ALB, EventBridge scheduler, GitHub Actions OIDC deploy role |
| **CI/CD** | GitHub Actions — lint → build → push to ECR → force-deploy ECS → wait stable; OIDC auth, no stored AWS keys |

## Project layout

```
services/
  ingestion/      — FastAPI: validates events, publishes to Kinesis
  consumer/       — Long-running: reads Kinesis, writes Parquet to S3
  analytics-api/  — FastAPI: serves gold metrics, Athena/Redshift engines
  load_gen/       — Async load generator

shared/           — Shared event schema + base settings (imported by all services)

jobs/
  silver/         — Athena SQL: bronze → silver (dedupe, type)
  gold/           — Athena SQL: silver → gold (DAU, top pages, etc.)
  redshift/       — Redshift TRUNCATE + COPY: gold → mart tables

infra/            — CDK stacks (VPC, lake, stream, compute, scheduler, pipeline)
scripts/          — Local bootstrap (creates Kinesis stream, S3 bucket, Glue tables)
dashboard/        — Static HTML + Chart.js served by Analytics API
```

## Documentation

- **[Architecture](docs/ARCHITECTURE.md)** — event model, data lake layout,
  system flows, component diagram, failure & recovery, design decisions
- **[Development](docs/DEVELOPMENT.md)** — local setup, load testing,
  experiments (Parquet compression, batch size, partition pruning)
