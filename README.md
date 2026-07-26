# Product Analytics Platform

An end-to-end streaming analytics platform: product events flow through
Kinesis, land as partitioned Parquet in a Data Lake, and get served back as
analytics. Built to demonstrate core **data engineering concepts** — streaming
ingestion, medallion architecture, columnar storage, partitioning — rather
than another CRUD app.

## Goal

Stream product events end-to-end and **measure** how much Parquet,
partitioning, and batching actually improve query performance and cost —
then serve the results as real analytics endpoints (DAU, top pages,
conversion, and more).

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
