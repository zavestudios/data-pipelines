# k3s to EKS Promotion Guide

This pipeline is designed for portability:

- Keep ETL code and DAG logic identical across environments.
- Use immutable image tags.
- Put environment differences in GitOps values/overlays only.

## k3s Baseline Checklist

- Airflow DAG `listings_ingest` is visible and schedulable.
- `KubernetesPodOperator` tasks run with expected image tag.
- Postgres connectivity is verified.
- Reject records are written to `ETL_REJECTS_PATH`.
- DQ stage passes for current `run_date`.

## EKS Hardening Checklist

- Service account is mapped with IRSA policy for required AWS access.
- Image pull path uses ECR credentials/policies.
- Network policies allow only required egress/ingress.
- Storage class and secret wiring match platform standards.
- End-to-end run output matches k3s semantics.

## Promotion Workflow

1. Build and publish ETL image tag (example: `zavestudios/etl-runner:0.1.0`).
2. Update k3s GitOps values to new tag and sync.
3. Run one scheduled/manual DAG execution and verify all three stages.
4. Promote the same image tag to EKS values.
5. Validate one EKS run.
6. If regression occurs, rollback by reverting GitOps image tag.
