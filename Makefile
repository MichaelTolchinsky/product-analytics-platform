.PHONY: up down build test lint load-test setup setup-shared setup-ingestion setup-consumer setup-analytics-api setup-load-gen bootstrap jobs-local jobs flush-cache

## Local dev
up:
	docker compose up floci -d
	@echo "Waiting for Floci to be healthy..."
	@until docker compose ps floci | grep -q "healthy"; do sleep 1; done
	uv run python scripts/bootstrap_local.py
	docker compose up ingestion consumer -d
	@echo "Waiting for ingestion to be ready..."
	@until curl -sf http://localhost:8000/docs > /dev/null 2>&1; do sleep 1; done
	TOTAL_EVENTS=5000 uv run python -m load_gen.runner
	uv run python jobs/runner_local.py
	docker compose up analytics-api -d

flush-cache:
	@echo "Flushing metrics-cache table..."
	AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
	  aws --endpoint-url=http://localhost:4566 --region eu-north-1 \
	  dynamodb delete-table --table-name metrics-cache 2>/dev/null || true
	@sleep 1
	uv run python scripts/bootstrap_local.py

down:
	docker compose down -v

build:
	docker compose build

bootstrap:
	uv run python scripts/bootstrap_local.py

## Install deps locally (for IDE support + running outside Docker)
setup: setup-shared setup-ingestion setup-consumer setup-analytics-api setup-load-gen

setup-shared:
	uv pip install -e shared/

setup-ingestion:
	uv pip install -e services/ingestion/

setup-consumer:
	uv pip install -e services/consumer/

setup-analytics-api:
	uv pip install -e services/analytics-api/

setup-load-gen:
	uv pip install -e services/load_gen/

## Testing
test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

lint-fix:
	uv run ruff check --fix .
	uv run ruff format .

## Load testing
load-test:
	uv run python -m load_gen.runner

## Jobs (local — DuckDB direct, bypasses Athena)
jobs-local:
	uv run python jobs/runner_local.py

## Jobs (production — Athena via real AWS)
jobs:
	AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_REGION=eu-north-1 AWS_DEFAULT_REGION=eu-north-1 AWS_ENDPOINT_URL=http://localhost:4566 uv run python jobs/runner.py

## CDK (local → Floci)
infra-bootstrap:
	cd infra && AWS_ENDPOINT_URL=http://localhost:4566 cdk bootstrap

infra-deploy:
	cd infra && AWS_ENDPOINT_URL=http://localhost:4566 cdk deploy --all

## CDK (real AWS)
infra-deploy-prod:
	cd infra && cdk deploy --all
