# Implementation Roadmap (k3s First, EKS Ready)

This roadmap documents the execution and learning plan for turning this
repository into a Kubernetes-native data pipeline application.

## Objectives

- Build a production-shaped Airflow ETL pipeline.
- Run first in `k3s` for fast feedback and learning.
- Promote to `EKS` with environment-specific hardening.
- Keep ETL logic portable across environments.

## Architecture Principles

- Same ETL code and DAG behavior in all environments.
- Environment differences live in GitOps values/overlays.
- Use immutable image tags (no `latest` promotion).
- Prioritize idempotent loads and observable operations.

## Delivery Timeline (6 Weeks)

## Week 1: Foundation and Contracts

- Introduce typed ETL models and validated configuration.
- Standardize a CLI job entrypoint.
- Harden container packaging and dependency pinning.
- Learning goals:
  - ETL lifecycle and pipeline stages.
  - Why schema/contracts reduce operational failures.
- Checkpoint:
  - Local CLI execution works with structured logs.

## Week 2: Data Reliability and Idempotency

- Implement PostgreSQL load path with upsert semantics.
- Define table contract and run-date uniqueness behavior.
- Add reject handling for malformed records with reason codes.
- Learning goals:
  - Idempotency, duplicate handling, and bad-record strategy.
- Checkpoint:
  - Re-running same date does not duplicate logical rows.

## Week 3: Orchestration with Airflow

- Build production DAG (`listings_ingest`) with stage chaining:
  - `extract_validate` -> `load_postgres` -> `dq_assertions`.
- Configure task runtime parameters and resource limits.
- Learning goals:
  - Orchestration vs execution.
  - Retries, backfills, and run semantics.
- Checkpoint:
  - DAG runs successfully and task logs are usable.

## Week 4: k3s Baseline via GitOps

- Wire image/tag and runtime config into k3s GitOps overlays.
- Validate namespace, permissions, secrets, and DB connectivity.
- Learning goals:
  - Declarative delivery and reconciliation.
- Checkpoint:
  - End-to-end daily run succeeds in k3s.

## Week 5: EKS Hardening and Parity

- Add EKS overlays with provider-specific deltas:
  - IRSA, ECR integration, storage/network/security policies.
- Validate behavior parity with k3s (same app contract, same outputs).
- Learning goals:
  - Portable app boundary vs provider-specific platform concerns.
- Checkpoint:
  - Same pipeline contract succeeds in EKS staging.

## Week 6: Operations and Promotion Workflow

- Add CI gates for tests and DAG parse validation.
- Define observability baseline and runbook procedures.
- Formalize promotion path:
  - validate in k3s -> promote same tag to EKS.
- Learning goals:
  - Reliability engineering for data pipelines.
  - Safe rollout and rollback workflows.
- Checkpoint:
  - Repeatable promotion with documented incident response.

## Public Interfaces and Contracts

- CLI:
  - `python -m etl.jobs.ingest_csv --input ... --run-date ... --batch-id ... --stage ...`
- Required env:
  - `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSLMODE`
  - `ETL_LOG_LEVEL`, `ETL_REJECTS_PATH`
- DAG:
  - `listings_ingest`
  - Tasks: `extract_validate`, `load_postgres`, `dq_assertions`
- Data sink contract:
  - Postgres `listings` keyed by `(address, run_date)`

## Testing Strategy

- Unit tests:
  - Normalization, reject logic, config validation.
- DAG tests:
  - Parse/import in CI.
- Integration tests:
  - Postgres write, idempotent reruns, DQ assertions.
- Environment tests:
  - k3s acceptance run before EKS promotion.

## Acceptance Criteria

- Pipeline runs end-to-end in k3s and EKS.
- Data loads are idempotent and auditable.
- Failures are diagnosable via logs and runbook.
- Promotion process is documented and repeatable.

## Related Documents

- `README.md`
- `docs/k3s-eks-promotion.md`
- `docs/operations-runbook.md`
