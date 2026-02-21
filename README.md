# ZaveStudios Airflow ETL

This repository contains Airflow DAGs and ETL job code for a Kubernetes-native batch pipeline.

## What Runs Here

- DAG: `dags/listings_ingest.py`
- Job entrypoint: `python -m etl.jobs.ingest_csv`
- Stages:
  - `extract_validate`
  - `load_postgres`
  - `dq_assertions`

## Required Environment Variables

- `DB_HOST`
- `DB_PORT` (default: `5432`)
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_SSLMODE` (default: `prefer`)
- `ETL_LOG_LEVEL` (default: `INFO`)
- `ETL_REJECTS_PATH` (default: `/tmp/rejects.ndjson`)

## Local Execution

Run the full load stage:

```bash
python -m etl.jobs.ingest_csv \
  --input data/listings.csv \
  --run-date 2026-02-11 \
  --batch-id local-dev \
  --stage load_postgres
```

Run validation only:

```bash
python -m etl.jobs.ingest_csv \
  --input data/listings.csv \
  --run-date 2026-02-11 \
  --batch-id local-dev \
  --stage extract_validate
```

## Tests

```bash
pytest -q
```

## Container Build

```bash
docker build -t zavestudios/etl-runner:0.1.0 .
```

## Docker Compose (Local Pipeline)

Run the default load stage (`load_postgres`) with local Postgres:

```bash
docker compose up --build etl-load-postgres
```

Run validation-only stage:

```bash
docker compose --profile validate up --build etl-extract-validate
```

Run DQ assertions stage:

```bash
docker compose --profile dq up --build etl-dq-assertions
```

Stop and clean up:

```bash
docker compose down -v
```

## Local Airflow UI with Compose

Start Airflow + Postgres:

```bash
docker compose up --build airflow
```

Then open `http://localhost:8080`.

The `standalone` startup prints the initial username/password in container logs:

```bash
docker compose logs airflow
```

The compose Airflow service sets `ETL_EXECUTION_BACKEND=local`, so the same
`listings_ingest` DAG runs with local `BashOperator` tasks instead of
`KubernetesPodOperator`. This lets you learn the DAG flow locally while keeping
the Kubernetes execution path for k3s/EKS.

To run:

1. Unpause DAG `listings_ingest`.
2. Trigger a DAG run from the UI.
3. Inspect task logs for `extract_validate`, `load_postgres`, `dq_assertions`.

## Deployment Model

- Airflow runs in Kubernetes (k3s first, EKS target).
- This repo builds the ETL image and DAG logic.
- GitOps repo owns environment-specific runtime config and promotion.

## DAG Deployment Strategy

This repository supports two DAG delivery models:

1. Baked into image
- DAGs are copied into the ETL/Airflow image at build time.
- Rollouts are immutable because code and image tag move together.
- Best when you want strong promotion control (`k3s` -> `EKS`) with pinned tags.

2. Git-sync (future state)
- Airflow sidecars pull DAGs from Git at runtime.
- DAG iteration is faster because you can ship DAG-only changes.
- Requires stricter branch/tag controls to avoid drift from tested image versions.

Recommended default for this repo:
- Use baked-image DAGs for production promotion.
- Reserve Git-sync for rapid development workflows and explicit non-prod use.

Best practices:
- Keep DAG and ETL code changes in the same PR when behavior is coupled.
- Promote immutable tags only (avoid mutable `latest`).
- Treat DAG commits as production code: tests, review, and traceable issue links.

See:
- `docs/implementation-roadmap.md`
- `docs/k3s-eks-promotion.md`
- `docs/operations-runbook.md`
