# Product Analytics Platform

A small streaming analytics platform that ingests product events, stores them
efficiently in a Data Lake, and exposes analytical queries. The focus is on
**data engineering concepts**.

## Goal

Build an end-to-end pipeline that streams product events, lands them as
partitioned Parquet in a Data Lake, and serves analytics over the historical
data — while measuring the impact of Parquet, partitioning, and batching.

## Scope

- **Target completion:** 3–5 days
- **Budget:** ~$30–50 total estimated (Kinesis has no free tier: ~$0.015/shard-hr; ALB ~$0.008/LCU-hr; S3/Athena near-free at this scale). Tear down after experiments.

## Versions

The project is delivered in two milestones.

### v1 — Streaming lake + medallion (current scope)
- Ingestion → Kinesis → processing → **bronze** (raw Parquet) → **silver** (clean)
- Glue Data Catalog + Athena for **ad-hoc** and **scheduled aggregation** into gold
- Analytics API serves precomputed **gold** metrics on-demand
- Load generator + the Parquet / partitioning / batching experiments
- No warehouse, no frontend

### v2 — Warehouse serving + dashboard (future)
- Add **Redshift (Serverless)** as the gold/marts serving tier
- **Materialized-view** pattern: scheduled refresh of curated marts in Redshift
- Optional **serving cache** (DynamoDB/Redis) in front of Redshift for low-latency reads
- A simple **UI / dashboard** on top of the analytics API

## Documentation

- **[Architecture](docs/ARCHITECTURE.md)** — requirements, event model, data lake
  layout, system flows, component diagram, failure & recovery, success criteria
- **[Development](docs/DEVELOPMENT.md)** — tech stack, local dev setup (Floci),
  load testing, experiments
