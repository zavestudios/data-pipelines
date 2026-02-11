# Pipeline Operations Runbook

## DAG and Tasks

- DAG: `listings_ingest`
- Tasks:
  - `extract_validate`
  - `load_postgres`
  - `dq_assertions`

## Key Log Fields

- `stage`
- `batch_id`
- `run_date`
- `processed_rows`
- `normalized_rows`
- `rejected_rows`
- `db_processed`
- `db_upserted`

## Failure Triage

1. Validate task failure stage in Airflow UI.
2. Check pod logs for structured error details.
3. Confirm DB env vars/secrets are present.
4. Verify input file path exists and is readable.
5. Re-run the failed task.

## Common Failures

- `missing_address` / `invalid_price` / `negative_price`:
  - Inspect rejects output.
  - Fix source data or upstream mapping.
- Database connection errors:
  - Validate host/port/credentials and policy routing.
- DQ assertion failure (`no rows loaded for run_date`):
  - Confirm prior load stage completed.
  - Check source volume/input path for empty data.

## Backfill Procedure

1. Trigger DAG for historical date range.
2. Monitor `load_postgres` and `dq_assertions` for each run.
3. Because loader is idempotent on `(address, run_date)`, reruns are safe.

## Rollback

1. Revert GitOps image tag to prior known-good version.
2. Sync cluster state.
3. Trigger single verification run.
