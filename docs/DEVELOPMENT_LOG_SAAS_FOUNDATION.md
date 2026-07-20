# Development Log: FreshSense 0.6 SaaS Foundation

## Objective

Begin moving FreshSense from a single-user scanner into a reviewable produce
inspection workflow for small grocery stores and produce teams.

## Implemented

- Added a workspace-scoped SQLite repository in `saas/store.py`.
- Added persisted locations, inspection metadata, review state, and append-only
  review events.
- Added FastAPI endpoints for workspace context, inspection analysis, inspection
  listing, human review, and dashboard summaries.
- Reused the existing model, supported-input gate, semantic retrieval, reasoning,
  warnings, and recommendation pipeline.
- Kept images and filenames out of the SaaS database.
- Derived a stable, non-secret workspace identity from the authenticated API
  principal.
- Enforced workspace ownership when listing or reviewing an inspection.
- Added typed OpenAPI contracts and automated isolation and workflow tests.

## API additions

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/workspace` | Return the authenticated pilot workspace and locations |
| `GET` | `/api/v1/dashboard` | Return real inspection and review aggregates |
| `GET` | `/api/v1/inspections` | List metadata visible to the authenticated workspace |
| `POST` | `/api/v1/inspections/analyze` | Analyze a photo and save result metadata |
| `PATCH` | `/api/v1/inspections/{inspection_id}/review` | Confirm, correct, or dismiss one result |

## Security and privacy behavior

- Protected routes reject an invalid API key before parsing multipart uploads.
- A workspace cannot list or review another workspace's records.
- API keys are hashed before they are used as internal identity material.
- Uploaded images are closed after inference and are never written by the SaaS
  store.
- Saved records explicitly report `image_retained: false`.
- Existing upload limits, decoded pixel limits, trusted hosts, CORS controls,
  rate limits, request IDs, and security headers remain active.

## Current limitation

The foundation uses API keys to test a tenant boundary. It does not yet provide
customer registration, user sessions, membership roles, or Microsoft Entra
External ID. It must not be described as a publicly hosted multi-user SaaS until
those controls and a production database are configured and tested.

## Next increment

Implement Entra-backed user identity and role-aware organization membership,
then build the responsive web workspace against these endpoints. Replace the
SQLite repository with PostgreSQL before a hosted pilot, while keeping the same
API contracts and privacy defaults.
