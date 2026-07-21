# FreshSense read-only MCP integration

FreshSense includes an optional Model Context Protocol gateway for developer
experiments and partner integrations. It uses `mcp-use==1.7.0` and exposes one
typed tool, `get_recent_inspections`, which retrieves recent inspection metadata
from the caller's authenticated FreshSense workspace.

The gateway is deliberately narrow. It cannot upload or analyze images, change
reviews, create tasks, approve actions, or send notifications. It calls only the
existing `GET /api/v1/inspections` endpoint.

## Install the optional runtime

Python 3.11 or newer is required. The MCP dependencies are separate from the
main API runtime.

```powershell
py -3.11 -m venv .mcp-venv
& .\.mcp-venv\Scripts\python.exe -m pip install -r requirements-mcp.txt
$env:FRESHSENSE_MCP_API_URL='http://127.0.0.1:8000'
$env:FRESHSENSE_MCP_API_KEY='<local-development-key>'
$env:MCP_USE_ANONYMIZED_TELEMETRY='false'
& .\.mcp-venv\Scripts\python.exe -m freshsense_mcp.server --transport stdio
```

`FRESHSENSE_MCP_API_URL` must be an absolute HTTP or HTTPS URL. Configure
exactly one credential:

- `FRESHSENSE_MCP_API_KEY` for a FreshSense API key; or
- `FRESHSENSE_MCP_BEARER_TOKEN` for an OAuth access token.

Startup fails if neither or both are configured. Credentials are forwarded to
the FreshSense API and are not included in tool output or authentication errors.
Use plain HTTP only for a loopback development API such as `127.0.0.1` or
`localhost`; remote FreshSense API targets should use HTTPS.
`MCP_USE_ANONYMIZED_TELEMETRY=false` is also the process default, but setting it
explicitly makes the local configuration clear.

## Tool contract

`get_recent_inspections` accepts:

- `limit`: 1 through 50, default 10; and
- `review_status`: optional `pending`, `confirmed`, `corrected`, or `dismissed`.

The result contains a count and the following fields for each inspection:

`inspection_id`, `created_at_utc`, `location_name`, `batch_reference`,
`decision`, `analysis_status`, `predicted_display_name`, `fruit`,
`predicted_freshness`, `confidence`, `risk_level`, `review_status`, and
`reviewed_outcome`.

Photos, filenames, operator notes, and review notes are omitted. The server
marks the tool with `readOnlyHint=true` and `destructiveHint=false`. These
annotations help MCP clients understand intent, but the annotation does not replace API authorization.
Workspace isolation and access decisions remain in the authenticated FreshSense
REST API.

## Local HTTP inspection

For local development, start the streamable HTTP transport on loopback:

```powershell
& .\.mcp-venv\Scripts\python.exe -m freshsense_mcp.server `
  --transport streamable-http --host 127.0.0.1 --port 8010 --debug
```

Open `http://127.0.0.1:8010/inspector` to inspect and call the tool. The MCP
protocol endpoint is `http://127.0.0.1:8010/mcp`. Both `/inspector` and `/mcp`
are local development endpoints unless a separate authenticated deployment is
designed and reviewed. This feature is not a public unauthenticated endpoint.

## Reproducible client smoke test

Install the development requirements, disable telemetry, and run the
self-contained smoke script:

```powershell
& .\.mcp-venv\Scripts\python.exe -m pip install -r requirements-mcp-dev.txt
$env:MCP_USE_ANONYMIZED_TELEMETRY='false'
& .\.mcp-venv\Scripts\python.exe scripts/smoke_mcp_integration.py
```

The script starts a localhost stub FreshSense API, launches the MCP server over
stdio, uses an `mcp-use` client to discover the tool, calls it, and prints one
minimized inspection. It does not contact the hosted FreshSense service.

## Security boundary

- The REST API remains responsible for authentication, role checks, and
  workspace isolation.
- The MCP layer performs input validation and response minimization.
- Only `GET /api/v1/inspections` is available through this gateway.
- Free-form staff text and image data do not cross the MCP boundary.
- Run streamable HTTP on loopback for development. A public deployment requires
  separate authentication, rate limiting, logging, and threat review.
