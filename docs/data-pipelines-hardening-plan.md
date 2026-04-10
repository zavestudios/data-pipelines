# Production Hardening Plan: `listings-ingest`

## Objective

Harden `listings-ingest` for production deployment by:

- reducing container attack surface
- enforcing non-root, read-only runtime defaults
- moving database secrets to the platform Vault -> External Secrets Operator -> Kubernetes Secret path
- adding defense-in-depth image scanning beyond the current Trivy baseline

## Repository Scope

Based on [`REPO_TAXONOMY.md`](/Users/xavierlopez/Dev/platform-docs/_platform/REPO_TAXONOMY.md):

- `listings-ingest` is a `tenant` repository
- `gitops` is an `infrastructure` repository
- `platform-pipelines` is a `platform-service` repository

This hardening effort is cross-repo in implementation, even though this document is only a planning artifact.

## Current State

### Working Today

- DAG already uses `KubernetesPodOperator` with `in_cluster=True`
- Runtime is parameterized with env vars such as `NAMESPACE`, `ETL_IMAGE`, and `INPUT_PATH`
- Dockerfile already runs as a non-root user on a slim base image
- CI already runs Trivy scanning

### Gaps

- no service account for IRSA-compatible secret access patterns
- missing hardened pod and container security context
- secrets still rely on environment-variable style configuration rather than the platform Vault -> ESO -> K8s Secret pattern
- Docker image is still based on Debian slim rather than a distroless runtime
- CI only uses Trivy and does not validate distroless/STIG-style runtime properties

## Recommended Approaches

### Container Hardening

Use a multi-stage build with `gcr.io/distroless/python3-debian12` as the runtime image.

Why:

- removes shell and package manager from the final image
- reduces runtime attack surface
- aligns well with read-only filesystem enforcement
- fits the current `KubernetesPodOperator` execution model

Proposed strategy:

- builder stage: `python:3.11-slim`
- runtime stage: `gcr.io/distroless/python3-debian12`
- run as UID/GID `1000:1000`
- mount writable paths such as `/tmp` and `/app/.cache` explicitly

Deferred unless required later:

- FIPS-specific base image work
- Iron Bank base image migration

### Security Scanning

Add Grype plus a lightweight custom STIG-style audit script.

Why:

- Grype gives a second vulnerability data source alongside Trivy
- a custom audit can validate distroless-specific properties that CVE scanners do not cover
- this is more practical than OpenSCAP for a Debian-based distroless image

Target checks:

- no shell present
- non-root execution
- no setuid/setgid binaries
- minimal runtime file surface

## Implementation Plan

### Phase 1: Dockerfile Hardening

Schedule: Week 1, Days 1-3

Repository: `listings-ingest`

File:

- `/Users/xavierlopez/Dev/listings-ingest/Dockerfile`

Planned changes:

```dockerfile
# Stage 1: Builder
FROM python:3.11-slim AS builder
WORKDIR /app
ARG AIRFLOW_VERSION=2.9.3
ARG PYTHON_VERSION=3.11
ARG AIRFLOW_CONSTRAINTS_URL=https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -c "${AIRFLOW_CONSTRAINTS_URL}" -r requirements.txt

COPY etl/ ./etl/
COPY scripts/ ./scripts/
COPY dags/ ./dags/

RUN python -m compileall -b /app

# Stage 2: Runtime
FROM gcr.io/distroless/python3-debian12:latest
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app /app

USER 1000:1000
ENTRYPOINT ["python"]
```

Also update:

- `/Users/xavierlopez/Dev/listings-ingest/docker-compose.yml`

Recommended local runtime settings:

```yaml
tmpfs:
  - /tmp
  - /app/.cache
read_only: true
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
user: "1000:1000"
```

Validation:

1. `docker build -t etl-runner:hardened .`
2. `docker run --rm etl-runner:hardened /bin/sh` should fail
3. `docker run --rm etl-runner:hardened -m etl.jobs.ingest_csv --help`
4. `docker compose up --build etl-load-postgres`

### Phase 2: DAG Security Context

Schedule: Week 1, Days 3-4

Repository: `listings-ingest`

File:

- `/Users/xavierlopez/Dev/listings-ingest/dags/listings_ingest.py`

Planned changes:

```python
SECURITY_CONTEXT = k8s.V1PodSecurityContext(
    run_as_user=1000,
    run_as_group=1000,
    fs_group=1000,
    run_as_non_root=True,
)

CONTAINER_SECURITY_CONTEXT = k8s.V1SecurityContext(
    run_as_non_root=True,
    allow_privilege_escalation=False,
    read_only_root_filesystem=True,
    capabilities=k8s.V1Capabilities(drop=["ALL"]),
)

VOLUME_MOUNTS = [
    k8s.V1VolumeMount(name="tmp", mount_path="/tmp"),
    k8s.V1VolumeMount(name="cache", mount_path="/app/.cache"),
]

VOLUMES = [
    k8s.V1Volume(name="tmp", empty_dir=k8s.V1EmptyDirVolumeSource()),
    k8s.V1Volume(name="cache", empty_dir=k8s.V1EmptyDirVolumeSource()),
]
```

Update each `KubernetesPodOperator` task to include:

- `service_account_name`
- `security_context`
- `container_security_context`
- `volume_mounts`
- `volumes`

Validation:

1. `python -m py_compile dags/listings_ingest.py`
2. Local Airflow mode remains unchanged for BashOperator paths
3. Requires cluster access: `kubectl get pod <name> -o yaml`

### Phase 3: Secrets Integration

Schedule: Week 1, Day 5 through Week 2, Day 2

Repository: `listings-ingest`

Prerequisite:

- GitOps manifests from Phase 5 must be deployed first

File:

- `/Users/xavierlopez/Dev/listings-ingest/dags/listings_ingest.py`

Planned changes:

```python
def _secret_env_vars() -> list[k8s.V1EnvVar]:
    """Build env vars from K8s Secret sourced by External Secrets Operator."""
    secret_name = "listings-ingest-db"
    keys = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_SSLMODE"]
    return [
        k8s.V1EnvVar(
            name=key,
            value_from=k8s.V1EnvVarSource(
                secret_key_ref=k8s.V1SecretKeySelector(
                    name=secret_name,
                    key=key,
                )
            ),
        )
        for key in keys
    ]
```

Update each `KubernetesPodOperator` task:

```python
extract_validate = KubernetesPodOperator(
    # ... existing config ...
    env_vars=_secret_env_vars(),
    # ... rest of config ...
)
```

Validation:

1. Requires cluster access: `kubectl get externalsecret -n listings-ingest`
2. Requires cluster access: `kubectl get secret listings-ingest-db -n listings-ingest -o yaml`
3. Trigger a DAG run and verify database connectivity

### Phase 4: CI/CD Scanning Enhancements

Schedule: Week 1, Days 4-5

#### 4.1 Platform workflow enhancement

Repository: `platform-pipelines`

File:

- `/Users/xavierlopez/Dev/platform-pipelines/.github/workflows/container-build.yml`

Proposed additions:

```yaml
inputs:
  grype_enabled:
    description: "Enable Grype CVE scanning"
    type: boolean
    default: false
  stig_audit_enabled:
    description: "Enable custom STIG audit script"
    type: boolean
    default: false
```

Add:

- a Grype scan step after Trivy
- optional SARIF upload if scan output is captured that way
- a hook for a custom STIG audit script

#### 4.2 Custom audit script

Repository: `listings-ingest` or `platform-pipelines`

Suggested file:

- `/Users/xavierlopez/Dev/listings-ingest/scripts/stig_audit.py`

Suggested checks:

```python
def audit_image(image_ref: str) -> bool:
    checks = [
        ("No shell present", check_no_shell),
        ("Non-root user", check_non_root),
        ("No setuid binaries", check_no_setuid),
        ("Minimal file count", check_minimal_files),
    ]
    failures = [name for name, fn in checks if not fn(image_ref)]
    if failures:
        print(f"STIG audit failed: {', '.join(failures)}")
        return False
    print("STIG audit passed")
    return True
```

#### 4.3 Consumer workflow update

Repository: `listings-ingest`

File:

- `/Users/xavierlopez/Dev/listings-ingest/.github/workflows/build.yml`

Planned changes:

```yaml
permissions:
  contents: read
  packages: write
  id-token: write
  security-events: write

jobs:
  build:
    uses: zavestudios/platform-pipelines/.github/workflows/container-build.yml@main
    with:
      image_name: ${{ github.repository_owner }}/zavestudios-etl-runner
      dockerfile: Dockerfile
      push: ${{ github.ref == 'refs/heads/main' }}
      platforms: linux/amd64
      fail_severity: CRITICAL
      grype_enabled: true
      stig_audit_enabled: true
    secrets:
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Phase 5: GitOps Manifests

Schedule: Week 2, Days 1-3

Repository: `gitops`

These manifests belong in `gitops`, not `listings-ingest`.

#### 5.1 Namespace

Path:

- `/Users/xavierlopez/Dev/gitops/tenants/listings-ingest/namespace.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: listings-ingest
  labels:
    zave.io/workload: listings-ingest
```

#### 5.2 ServiceAccount

Path:

- `/Users/xavierlopez/Dev/gitops/tenants/listings-ingest/serviceaccount.yaml`

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: listings-ingest
  namespace: listings-ingest
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT_ID:role/listings-ingest-secrets-reader
```

#### 5.3 ExternalSecret

Path:

- `/Users/xavierlopez/Dev/gitops/tenants/listings-ingest/listings-ingest-db.external-secret.yaml`

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: listings-ingest-db
  namespace: listings-ingest
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: ClusterSecretStore
    name: vault-kv
  target:
    name: listings-ingest-db
    creationPolicy: Owner
  data:
    - secretKey: DB_HOST
      remoteRef:
        key: tenants/listings-ingest/db
        property: DB_HOST
    - secretKey: DB_PORT
      remoteRef:
        key: tenants/listings-ingest/db
        property: DB_PORT
    - secretKey: DB_NAME
      remoteRef:
        key: tenants/listings-ingest/db
        property: DB_NAME
    - secretKey: DB_USER
      remoteRef:
        key: tenants/listings-ingest/db
        property: DB_USER
    - secretKey: DB_PASSWORD
      remoteRef:
        key: tenants/listings-ingest/db
        property: DB_PASSWORD
    - secretKey: DB_SSLMODE
      remoteRef:
        key: tenants/listings-ingest/db
        property: DB_SSLMODE
```

#### 5.4 Kustomization

Path:

- `/Users/xavierlopez/Dev/gitops/tenants/listings-ingest/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - serviceaccount.yaml
  - listings-ingest-db.external-secret.yaml
```

#### 5.5 Argo CD Application

Path:

- `/Users/xavierlopez/Dev/gitops/platform/argocd/applications/listings-ingest.yaml`

Use the standard Argo CD tenant-application pattern from [`GITOPS_MODEL.md`](/Users/xavierlopez/Dev/platform-docs/_platform/GITOPS_MODEL.md), pointing `spec.source.path` to `tenants/listings-ingest`.

## Implementation Sequence

### Week 1: Local Development and CI

#### Day 1-2

1. Rewrite the Dockerfile as a multi-stage distroless build.
2. Update `docker-compose.yml` for read-only local execution.
3. Validate local ETL execution.

#### Day 3-4

1. Add security context and writable volumes to `listings_ingest.py`.
2. Confirm DAG parseability.
3. Leave K8s runtime wiring for after GitOps secret setup.

#### Day 4-5

1. Create the STIG audit script.
2. Propose `platform-pipelines` workflow changes.
3. Enable the new scanners in `listings-ingest`.
4. Push branch and verify CI passes.

### Week 2: GitOps and Integration

#### Day 6-7

1. Add namespace, service account, ExternalSecret, and kustomization manifests in `gitops`.
2. Requires cluster access: populate Vault secrets.
3. Commit GitOps changes and wait for reconciliation.
4. Requires cluster access: verify `ExternalSecret` readiness.

#### Day 8

1. Update `listings_ingest.py` to read DB credentials from the Kubernetes Secret.
2. Commit `listings-ingest` changes.

#### Day 9

1. Merge `listings-ingest` PR and build the hardened image.
2. Update GitOps to reference the new image.
3. Trigger the Airflow DAG.
4. Validate hardened pod startup, secret injection, ETL completion, and filesystem behavior.

#### Day 10

1. If needed, create IAM role wiring for IRSA-based access.
2. Test in EKS staging if available.

## Testing Strategy

### Dockerfile

- `docker build -t etl-runner:test .`
- `docker run --rm etl-runner:test /bin/sh`
- `docker run --rm etl-runner:test -m etl.jobs.ingest_csv --help`
- `docker compose up --build etl-load-postgres`

### DAG

- `python -m py_compile dags/*.py`
- local Airflow execution through docker-compose mode
- k3s integration through GitOps deployment and DAG execution

### Secrets

- Requires cluster access: `kubectl get externalsecret -n listings-ingest`
- Requires cluster access: `kubectl get secret listings-ingest-db -n listings-ingest -o yaml`
- Requires cluster access: `kubectl exec -n airflow <pod> -- env | grep DB_`

### Security

- `trivy image ghcr.io/.../etl-runner:<tag>`
- Grype results from CI
- `python scripts/stig_audit.py ghcr.io/.../etl-runner:<tag>`

## Manual Steps

These steps require human or cluster-side action and are not repo-only changes:

- Requires cluster access: deploy or reconcile the GitOps manifests
- Requires cluster access: confirm External Secrets Operator is authorized to read the tenant secret path
- Requires cluster access: populate Vault at `tenants/listings-ingest/db`
- Requires cluster access: validate runtime behavior in k3s or EKS
- create IAM role wiring if IRSA is used

## Success Criteria

### End of Week 1

- distroless Dockerfile builds successfully
- DAG parses with hardened security settings
- CI passes with Trivy, Grype, and STIG audit enabled
- local docker-compose execution works with read-only filesystem settings

### End of Week 2

- GitOps manifests are deployed
- Vault secrets are populated
- DAG runs successfully in k3s with hardened pod settings
- secrets are injected from Kubernetes Secret rather than `.env`
- read-only filesystem is enforced without runtime failures
- production image reports zero critical CVEs
- STIG audit passes

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Distroless image breaks Python dependencies | Validate locally first and keep the builder/runtime split explicit |
| Read-only filesystem causes write errors | Mount `/tmp` and `/app/.cache` explicitly and test locally with read-only settings |
| IRSA is misconfigured | Treat Vault -> ESO as primary and IRSA as environment-specific follow-up |
| Vault secrets are not populated | Make secret creation and validation an explicit pre-deploy checklist item |

