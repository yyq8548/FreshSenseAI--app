# Microsoft Entra External ID setup

FreshSense supports customer sign-in through Microsoft Entra External ID. The
React client obtains an access token for the FreshSense API. FastAPI validates
that token's signature, issuer, audience, tenant, scope, and optional calling
client before a workspace request is accepted.

The browser never receives the FastAPI API key or a client secret.

## 1. Create the External ID tenant

Create or select a Microsoft Entra External ID tenant for customers. Record:

- the tenant ID;
- the tenant subdomain used by `ciamlogin.com`;
- the tenant authority, for example
  `https://freshsense.ciamlogin.com/<tenant-id>`.

Create a sign-up and sign-in user flow and select the identity providers and
attributes appropriate for the pilot. FreshSense uses the token subject and
tenant as the stable account identity. It uses `emails`, `email`, or
`preferred_username` only for the invitation match and display.

## 2. Register the FreshSense API

Create an app registration for the FastAPI service.

1. Open **Expose an API**.
2. Set an application ID URI, normally `api://<api-client-id>`.
3. Add the delegated scope `access_as_user`.
4. Allow users and administrators to consent according to the pilot policy.
5. Record the API application client ID.

The API expects the access token audience to equal this client ID. Do not send
an ID token to FastAPI.

## 3. Register the single-page application

Create a separate app registration for the React client.

1. Add the **Single-page application** platform.
2. Add `http://localhost:5173` as a local redirect URI. Microsoft Entra
   permits HTTP for `localhost` during local development, but rejects the
   equivalent `http://127.0.0.1` SPA callback.
3. Add the exact HTTPS redirect URI used by the future hosted web client.
4. Add the API delegated permission
   `api://<api-client-id>/access_as_user`.
5. Grant consent as required by the tenant policy.
6. Record the SPA application client ID.

Do not create or embed a client secret in the React application. A browser
application cannot protect one.

## 4. Configure FastAPI

In PowerShell, set values for the API process:

```powershell
$env:FRESHSENSE_AUTH_MODE = "entra"
$env:FRESHSENSE_ENTRA_TENANT_ID = "<tenant-id>"
$env:FRESHSENSE_ENTRA_API_CLIENT_ID = "<api-client-id>"
$env:FRESHSENSE_ENTRA_AUTHORITY = "https://<tenant-subdomain>.ciamlogin.com/<tenant-id>"
$env:FRESHSENSE_ENTRA_REQUIRED_SCOPE = "access_as_user"
$env:FRESHSENSE_ENTRA_ALLOWED_CLIENT_IDS = "<spa-client-id>"
$env:FRESHSENSE_CORS_ORIGINS = "http://localhost:5173"
$env:FRESHSENSE_ALLOWED_HOSTS = "127.0.0.1,localhost"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

`FRESHSENSE_ENTRA_ALLOWED_CLIENT_IDS` is recommended. It restricts accepted
delegated tokens to the listed SPA client IDs by checking `azp` or `appid`.

## 5. Configure and run the React client

Copy `web/.env.example` to `web/.env.local` and replace every placeholder:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_ENTRA_CLIENT_ID=<spa-client-id>
VITE_ENTRA_TENANT_ID=<tenant-id>
VITE_ENTRA_TENANT_SUBDOMAIN=<tenant-subdomain>
VITE_ENTRA_API_SCOPE=api://<api-client-id>/access_as_user
```

Then run:

```powershell
cd web
pnpm install --frozen-lockfile
pnpm dev
```

Open `http://localhost:5173`. If configuration is missing, FreshSense displays
a configuration-required screen instead of a simulated login.

## 6. Role and invitation behavior

- The first authenticated account that creates a workspace becomes manager.
- A manager can create inspector or reviewer invitations.
- The invitation is bound to the signed-in account email and expires after the
  configured period.
- The raw invitation token is returned only when created. SQLite stores only a
  SHA-256 hash.
- An inspector can record inspections but cannot submit reviews.
- A reviewer can submit reviews but cannot run inspections.
- A manager can perform both actions and invite members.

For the current local staging implementation, each identity belongs to one
workspace. Accept an invitation through its link before opening the workbench as
a new user, because a standalone first visit creates a new pilot workspace.

## Security verification

Before a hosted pilot:

- verify the authority and registered redirect URIs are exact;
- keep FastAPI behind HTTPS;
- set only approved web origins and hostnames;
- confirm the API rejects expired, wrong-tenant, wrong-audience, wrong-scope,
  wrong-client, and incorrectly signed tokens;
- review user-flow policies, consent, account deletion, and support ownership;
- migrate workspace storage from local SQLite to managed PostgreSQL; and
- add centralized revocation, monitoring, alerting, backups, and incident
  procedures.

Microsoft references:

- [External ID for customers overview](https://learn.microsoft.com/en-us/entra/external-id/customers/overview-customers-ciam)
- [Access-token validation](https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens)
- [Expose a web API](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-configure-app-expose-web-apis)
- [Configure a client to access a web API](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-configure-app-access-web-apis)
