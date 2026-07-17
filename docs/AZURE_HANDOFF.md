# Azure deployment handoff

FreshSense is not currently approved for Azure deployment. The repository
contains a fail-closed readiness gate so missing evidence cannot be mistaken for
approval.

## Proposed non-container architecture

The Technology team can deploy the FastAPI source to an approved managed Python
web runtime without requiring the project owner to operate Docker. A proposed
Azure design is:

```text
approved client
  -> managed identity/API authentication
  -> managed Python web application running FastAPI
  -> packaged immutable model and retrieval artifacts
  -> centralized secrets, logs, metrics, and alerts
```

No object storage is required for uploaded photographs because the API does not
retain them. Evaluation artifacts and approved model packages should live in an
access-controlled artifact repository selected by Technology.

## Required platform controls

- Entra-based identity or an approved API gateway; do not use shared static
  keys as the long-term control.
- Managed secrets and certificate rotation.
- TLS, restricted network access, allowlisted hosts/origins, and request limits.
- Centralized structured logging with image and personal-data exclusion.
- Application and model metrics, alerting, health probes, and rollback.
- Artifact checksum verification before the application becomes ready.
- Separate development, validation, and production environments.

## Readiness command

```powershell
python scripts\check_azure_readiness.py
```

The command requires:

1. an independent real-world evaluation report;
2. at least 400 supported and 400 unsupported test photographs;
3. false-fresh, unsupported-acceptance, coverage, and selective-accuracy targets;
4. at least 100 pilot records from five reviewers with usability evidence;
5. a machine-readable successful test record covering at least 100 tests;
6. business-owner, Technology-owner, and security-review approvals.

The current expected result is `blocked`. Passing the gate permits a
non-production Technology review only and never authorizes autonomous food
safety decisions.

## Deployment sequence after the gate passes

1. Technology validates the dependency lock, model manifest, and artifact
   checksums in a clean build environment.
2. Deploy the API to an isolated non-production environment.
3. Configure identity, secrets, network access, logs, metrics, and alerts.
4. Run OpenAPI, security, load, failure-recovery, and real-model smoke tests.
5. Review costs, latency, model behavior, privacy, and the rollback procedure.
6. Obtain explicit release approval; otherwise remove the environment.
