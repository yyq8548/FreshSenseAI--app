# Development log: SaaS identity and web workbench

## Goal

Replace the local SaaS foundation's temporary customer boundary with real
access-token validation, workspace roles, and a responsive authenticated web
client without introducing Docker or claiming a hosted release.

## Implemented

- Added Microsoft Entra External ID OIDC discovery and cached signing-key
  retrieval.
- Added JWT validation for RS256 signature, issuer, audience, expiry, issued-at,
  tenant, delegated scope, subject, and optional calling client.
- Preserved local and API-key modes for development and automated tests.
- Added manager, inspector, and reviewer workspace memberships.
- Added email-bound invitations with expiry, one-time acceptance, and hashed
  token storage.
- Added `/api/v1/me`, invitation creation, and invitation acceptance contracts.
- Enforced inspection and review permissions on the server, not only in the UI.
- Built a Fluent UI React workbench with Microsoft sign-in, real workspace
  metrics, inspection capture, review queue, member list, and invitation flow.
- Added loading, empty, configuration, authentication, and error states.
- Kept uploads ephemeral and excluded filenames and image bytes from SQLite.
- Added frontend configuration tests and a production bundle split into React,
  identity, Fluent UI, and application chunks.

## Current boundary

This is a working local staging increment, not a deployed SaaS. The web client
requires real Entra registrations and the API requires the real model assets.
SQLite remains appropriate for local workflow validation but is not the target
multi-instance production database.

## Recommended next increment

Prepare an Azure staging environment without Docker:

1. migrate the repository interface from SQLite to Azure Database for
   PostgreSQL;
2. deploy FastAPI directly to Azure App Service;
3. publish the static web client with HTTPS and exact redirect origins;
4. configure managed identity, Key Vault, Application Insights, rate limiting,
   backups, and alerts;
5. execute identity, authorization, privacy, load, and rollback tests; and
6. run a controlled store pilot before adding billing or more fruit classes.
