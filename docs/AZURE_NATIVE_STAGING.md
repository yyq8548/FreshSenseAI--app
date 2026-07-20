# Azure-native SaaS staging deployment

FreshSense can now run against local SQLite or managed PostgreSQL without
Docker. This guide prepares a **non-production staging environment** using:

- Azure Static Web Apps for the React workbench;
- Azure App Service on Linux for FastAPI and the vision model;
- Azure Database for PostgreSQL Flexible Server for workspace metadata; and
- the existing Microsoft Entra External ID customer tenant for sign-in.

No Azure resource has been created by these source changes. Creating App
Service, Static Web Apps, PostgreSQL, storage, or monitoring resources can incur
charges and requires a separate cost decision in the Azure subscription.

## Architecture and privacy boundary

```text
Browser
  -> Entra External ID sign-up/sign-in
  -> Azure Static Web Apps (React)
  -> HTTPS bearer token
  -> Azure App Service (FastAPI + one loaded model worker)
  -> Azure PostgreSQL (workspace and review metadata only)

App Service startup
  -> download immutable runtime bundle over HTTPS
  -> verify bundle SHA-256
  -> validate model/open-set association
  -> start API only when validation succeeds
```

Uploaded fruit photos are decoded in memory for the current request and are not
stored in PostgreSQL, the workbench, or object storage. The runtime artifact
location contains model files, not customer photos.

## Repository deployment assets

- `deployment/azure/startup.sh` verifies the runtime bundle and starts one
  Uvicorn worker. One worker avoids loading multiple large TensorFlow models in
  the same App Service instance.
- `deployment/azure/appservice.env.example` lists required App Service settings.
- `web/.env.production.example` lists build-time React settings.
- `web/public/staticwebapp.config.json` provides SPA routing and baseline
  browser security headers.
- `scripts/check_saas_staging_config.py` validates hosted settings without
  printing database credentials or signed artifact URLs.
- `scripts/migrate_saas_database.py` previews and applies a metadata-only
  migration into an empty PostgreSQL database.

## 1. Prepare the immutable model bundle

From the reviewed source tree, package the model, open-set gate, embedding
model, manifest, evaluation association, and golden test material:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package_runtime_bundle.ps1 `
  -GoldenSuite ci/golden `
  -OutputPath outputs/freshsense-runtime-0.6.0.zip
```

Upload the ZIP to an access-controlled HTTPS artifact location. Record the
published SHA-256. If a signed URL is used, store it only in App Service
settings and define a rotation procedure; never commit it.

## 2. Create staging resources in the Azure portal

Use a dedicated resource group and clear `-staging` names. Before creation,
review the displayed monthly estimate for each resource.

1. Create an Azure Database for PostgreSQL Flexible Server and a `freshsense`
   database. Require TLS and restrict network access to the API environment.
2. Create a Linux Azure App Service using a supported Python 3.11 runtime.
   Configure the startup command as:

   ```text
   bash deployment/azure/startup.sh
   ```

3. Copy the values from `deployment/azure/appservice.env.example` into App
   Service environment variables. Store the database password and artifact URL
   as secret application settings. Use `sslmode=verify-full` when the platform
   trust and DNS configuration support full certificate verification.
4. Create Azure Static Web Apps from the `web/` directory. Build with
   `pnpm install --frozen-lockfile` and `pnpm build`; publish `web/dist`.
   The committed `web/.env.production` supplies the public API and Microsoft
   Entra SPA configuration. Keep local-only overrides in `web/.env.local`.
5. For a different Azure environment, replace the five `VITE_*` values using
   `web/.env.production.example` as the template. They are public application
   identifiers and URLs, not client secrets.

The App Service source deployment must retain the repository root because Oryx
installs the root `requirements.txt`. Enable build automation with
`SCM_DO_BUILD_DURING_DEPLOYMENT=1`.

## 3. Complete hosted identity configuration

In the existing FreshSense SPA app registration:

1. Add the exact Static Web Apps HTTPS URL as a Single-page application redirect
   URI.
2. Keep `http://localhost:5173` only for local development.
3. Confirm the SPA still has delegated permission to
   `api://<api-client-id>/access_as_user`.
4. Put the hosted SPA client ID in
   `FRESHSENSE_ENTRA_ALLOWED_CLIENT_IDS` on App Service.
5. Set `FRESHSENSE_CORS_ORIGINS` to the exact Static Web Apps origin and
   `FRESHSENSE_ALLOWED_HOSTS` to the exact App Service hostname.

The browser must never receive an API client secret, database password, signed
artifact URL, or FastAPI shared key.

## 4. Validate configuration before deployment

Set the intended App Service values in a temporary shell, then run:

```powershell
python scripts/check_saas_staging_config.py
```

The command fails closed when it finds SQLite, HTTP/localhost CORS, wildcard
hosts, missing Entra restrictions, missing TLS, missing runtime checksum, or
disabled safety/observability controls. Passing this check validates
configuration only; it does not override the independent model and pilot gate
in `scripts/check_azure_readiness.py`.

## 5. Migrate existing workspace metadata

Keep the PostgreSQL database empty. Preview first:

```powershell
$env:FRESHSENSE_SAAS_DATABASE_URL = "<secret PostgreSQL URL>"
python scripts/migrate_saas_database.py `
  --source runtime/freshsense_saas.db
```

After reviewing counts, apply once and save the non-secret report:

```powershell
python scripts/migrate_saas_database.py `
  --source runtime/freshsense_saas.db `
  --apply `
  --output work/saas-migration-report.json
```

The migration refuses an occupied target, copies only known tenant-scoped
metadata tables, and verifies source and target row counts. It never migrates
photo bytes or local image paths.

## 6. Staging acceptance checks

Do not call the environment production until all of these pass:

1. `/api/v1/health` reports `database_backend: postgresql`, model loaded,
   authentication required, and semantic retrieval ready.
2. Anonymous, wrong-tenant, wrong-audience, wrong-scope, and wrong-client tokens
   are rejected.
3. A registered manager can analyze a supported sample, see it in the dashboard,
   invite a reviewer, and save a human review.
4. Cross-workspace access tests fail and photos are absent from database rows,
   logs, backups, and artifact storage.
5. App Service logs contain request IDs and structured metadata without access
   tokens, database URLs, signed URLs, image bytes, or user-entered notes.
6. Restart, rollback, database backup/restore, artifact checksum failure, and
   model startup failure are exercised.
7. The independent model reliability and controlled-pilot evidence remains
   visibly marked incomplete until it is genuinely complete.

## Production gaps that intentionally remain

- independent real-world model evidence and the full pilot threshold;
- security, privacy, business-owner, and Technology-owner approvals;
- centralized production monitoring, alerting, backup drills, and incident
  ownership;
- database credential replacement or rotation, ideally progressing to a
  reviewed managed-identity design; and
- an approved budget, load target, scaling policy, and rollback owner.

This staging path makes the SaaS workflow testable by invited users without
misrepresenting the model as an autonomous food-safety system.
