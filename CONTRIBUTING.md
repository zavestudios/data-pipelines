# Contributing

## Scope

This repository contains Airflow DAGs and ETL application code. Do not add
Kubernetes manifests, Terraform, or cluster provisioning logic here.

## Workflow

1. Open or reference an issue before starting work.
2. Create a feature branch from `main`.
3. Implement changes with tests and docs updates where needed.
4. Open a pull request linked to the issue.
5. Merge only after CI passes and review feedback is addressed.

## Branch Naming

Use one of these formats:

- `feature/<issue-number>-short-description`
- `fix/<issue-number>-short-description`
- `docs/<issue-number>-short-description`
- `chore/<issue-number>-short-description`

Examples:

- `feature/7-csv-ingest-modules`
- `docs/9-add-contributing-guide`

## Commit Guidelines

- Keep commits focused and atomic.
- Use imperative commit messages.
- Include issue references in commit body or PR description.

Example:

- `Add hello_k8s sample DAG`

## DAG Naming Conventions

- Use `snake_case` DAG IDs (for example `listings_ingest`).
- Keep task IDs stable and descriptive.
- Prefer explicit stage names (`extract_validate`, `load_postgres`, `dq_assertions`).

## Testing and CI Expectations

Before opening a PR, run:

```bash
pytest -q
```

Expected CI checks:

- DAG parse/import validation
- Unit tests for ETL code
- Image build workflow checks on PRs

## PR Checklist

- Issue linked
- Tests added/updated
- README/docs updated if behavior changed
- No infra manifests or unrelated files included
