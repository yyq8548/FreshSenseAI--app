# FreshSense technology handoff

## Purpose

This document gives a Technology team the information needed to assess and
continue FreshSense after prototype validation. It distinguishes implemented
prototype behavior from work required for production.

## System boundary

FreshSense supports one JPEG, PNG, or WebP image containing one visible apple,
banana, or orange. The default desktop workflow runs locally. The REST API
processes an upload in memory and does not retain the photograph or filename.

Core flow:

```text
image -> quality check -> scene check -> supported-input gate
      -> freshness classifier -> confidence/abstention
      -> curated retrieval -> reasoning -> recommendation
```

## Components

| Component | Implementation | Ownership concern |
|---|---|---|
| Desktop application | PySide6 Windows UI | Packaging, signing, update strategy |
| Vision inference | TensorFlow/Keras DenseNet201 | Model lifecycle and CPU capacity |
| Input-scope control | Calibrated feature-prototype gate | Independent OOD calibration |
| Explainability | Grad-CAM influence overlay | Human interpretation and QA |
| Knowledge retrieval | Local embeddings with keyword fallback | Knowledge review and refresh |
| Reasoning | Rule-based guidance with optional LLM path | Prompt/model governance |
| Integration API | FastAPI `/api/v1` | Authentication, rate limits, hosting |
| Pilot evidence | Local SQLite metadata store | Access control and retention policy |
| Evaluation | Versioned manifests and reports | Independent benchmark ownership |
| Release | PyInstaller/Inno Setup | Code signing and clean-machine testing |

## Runtime and dependencies

- Python and direct dependencies are pinned in the requirements files.
- TensorFlow and the embedding runtime are CPU-capable.
- The classifier, open-set gate, catalog, knowledge base, and evaluation report
  are cryptographically bound by `artifacts/model_manifest.json`.
- The Windows release is currently unsigned.
- MLflow is a development dependency used for comparison experiments; it is not
  required by the packaged inference runtime.

## API contract

- `GET /api/v1/health`: model and retrieval readiness.
- `GET /api/v1/metrics`: process-local operational metrics.
- `POST /api/v1/analyze`: validated in-memory image analysis.
- OpenAPI schema: `/openapi.json`.
- API-key authentication, trusted hosts, CORS allowlists, request IDs, rate
  limits, upload limits, structured logs, and safe error responses are
  available through configuration.

## Privacy and security

- Uploaded photographs and filenames are not persisted by the API.
- Desktop history stores result metadata, not the photograph.
- Pilot records use anonymized sample and reviewer identifiers.
- Secrets are read from environment variables or ignored local files.
- Production must add a managed identity/secret store, centralized audit logs,
  vulnerability management, access reviews, and an approved retention policy.

## AI governance and human oversight

- Unsupported or ambiguous images can be rejected without a freshness result.
- Grad-CAM is described as an influence visualization, not causal proof.
- All user surfaces state that internal spoilage and contamination cannot be
  determined from a photograph.
- A human must inspect the physical fruit before acting.
- Thresholds must be frozen on validation data before final test evaluation.

## Observability

Implemented process-local metrics include request counts, status counts,
analysis failures, active requests, and analysis latency. A hosted service must
export these to an approved monitoring platform and add:

- model/version and artifact checksum dimensions;
- rejection, uncertainty, and class-distribution rates;
- latency percentiles and resource saturation;
- data-drift and input-quality indicators without retaining sensitive images;
- alerts for authentication failures, elevated errors, and safety thresholds.

## Production-readiness gaps

1. Independent real-world model evaluation is incomplete.
2. Stakeholder pilot evidence is incomplete.
3. The Windows executable is not code-signed.
4. Centralized identity, secrets, logging, and monitoring are not configured.
5. Load, resilience, recovery, and penetration tests are incomplete.
6. Model approval, rollback, retraining ownership, and incident response require
   Technology and business owners.
7. Cloud deployment must remain blocked until the automated readiness gate
   passes and accountable owners approve the release.

## Proposed handoff artifacts

- Architecture and data-flow notes: this document and `README.md`.
- Stakeholder scope and acceptance criteria: `docs/STAKEHOLDER_CASE_STUDY.md`.
- Model evidence: `docs/MODEL_CARD.md` and `evaluation/reports/`.
- Reproducible dataset split: `evaluation/manifests/legacy_grouped_v1.json`.
- Artifact chain: `artifacts/model_manifest.json`.
- API and security tests: `tests/test_api*.py`.
- Windows release and clean-machine checks: `docs/WINDOWS_RELEASE.md`.
- Deployment decision gate: `scripts/check_azure_readiness.py`.

## Recommended Technology-team sequence

1. Review the use case, decision rights, and acceptance criteria.
2. Approve an independent data-collection and labeling protocol.
3. Reproduce training and evaluation from immutable manifests.
4. Review security, privacy, and AI-risk controls.
5. Run the limited pilot and approve or reject the readiness report.
6. Select the hosting pattern and observability platform.
7. Deploy to a non-production environment, validate, and retain a rollback path.
