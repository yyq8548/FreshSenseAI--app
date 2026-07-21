# FreshSense Read-Only MCP Integration Design

**Date:** 2026-07-21  
**Status:** Approved for implementation  
**Owner:** Yeqiao Yu

## Objective

Add a small, production-shaped Model Context Protocol integration to FreshSense using `mcp-use==1.7.0`. An MCP-compatible client must be able to retrieve recent inspection metadata without gaining any write capability or direct database access.

## User Story

As a developer evaluating FreshSense, I can connect an MCP client and call `get_recent_inspections` so that I can inspect recent workspace activity through a typed, documented, read-only interface.

## Chosen Architecture

The MCP server will be a thin gateway over the existing authenticated FreshSense REST API. It will call `GET /api/v1/inspections` instead of importing `SaaSStore` or connecting directly to PostgreSQL.

This boundary preserves the behavior that FreshSense already validates:

- authentication is enforced by the API;
- inspection results remain scoped to the caller's workspace;
- request validation and response contracts remain centralized;
- the MCP package does not need database credentials or schema knowledge; and
- the integration can target local, staging, or hosted FreshSense environments through configuration.

## Components

### `freshsense_mcp/client.py`

Contains a focused REST client responsible for:

- reading the configured FreshSense base URL;
- adding either an `X-API-Key` header or an OAuth bearer token;
- validating `limit` and `review_status` before a network request;
- calling only `GET /api/v1/inspections`;
- validating the expected JSON envelope; and
- converting transport, authentication, and response failures into concise integration errors that do not expose credentials.

The client will not contain MCP-specific code. This keeps HTTP behavior independently testable.

### `freshsense_mcp/server.py`

Creates an `mcp_use.MCPServer` and registers one tool:

```text
get_recent_inspections(limit: int = 10, review_status: str | None = None)
```

The tool will:

- use Python type hints and Pydantic field descriptions to produce a clear MCP schema;
- declare `ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)`;
- call the REST client;
- return a compact structured result containing `count` and `inspections`; and
- expose no write, review, approval, upload, or analysis operation.

The server will support `stdio` for desktop MCP clients and `streamable-http` for local inspection and smoke testing. Transport, host, and port will be selected by command-line arguments. Debug mode will default to off.

### `freshsense_mcp/config.py`

Loads and validates configuration from environment variables:

- `FRESHSENSE_MCP_API_URL`, required;
- `FRESHSENSE_MCP_API_KEY`, optional;
- `FRESHSENSE_MCP_BEARER_TOKEN`, optional.

Exactly one credential variable must be supplied. Secrets must never be logged, returned by tools, committed, or included in exception messages.

### Documentation and dependency isolation

`requirements-mcp.txt` will pin `mcp-use==1.7.0` separately from the existing API and desktop runtimes. `docs/MCP_INTEGRATION.md` will document configuration, stdio and HTTP startup, Inspector use, a direct client smoke test, the returned fields, and security limitations. The README will link to this guide without presenting the MCP integration as a write-capable Agent.

## Data Flow

1. An MCP client discovers `get_recent_inspections` through the MCP server.
2. The client calls the tool with `limit` and an optional `review_status`.
3. The MCP server validates the arguments and invokes the FreshSense REST client.
4. The REST client sends an authenticated `GET /api/v1/inspections` request.
5. The existing FreshSense API resolves the caller identity and workspace, then returns only that workspace's inspection metadata.
6. The MCP server emits a compact structured response to the MCP client.

No photo bytes, filenames, database credentials, or cross-workspace identifiers are introduced by this flow.

## Returned Fields

Each inspection result may contain only the fields already returned by the REST API that are useful for read-only operational context:

- `inspection_id`
- `created_at_utc`
- `location_name`
- `batch_reference`
- `decision`
- `analysis_status`
- `predicted_display_name`
- `fruit`
- `predicted_freshness`
- `confidence`
- `risk_level`
- `review_status`
- `reviewed_outcome`

The MCP response will not add stored images or filenames. It will omit free-form operator and review notes from the first version to reduce unnecessary disclosure.

## Validation and Failure Behavior

- `limit` must be between 1 and 50 for the MCP interface, even though the REST API permits a larger maximum.
- `review_status` may be `pending`, `confirmed`, `corrected`, or `dismissed`.
- Missing or ambiguous credentials fail at startup.
- HTTP 401 and 403 responses become a generic authentication or authorization error.
- Timeouts, unreachable hosts, non-JSON responses, and unexpected response shapes become concise MCP tool errors.
- Error messages include no API key, bearer token, Authorization header, or full response body.
- The integration performs no retry by default because the operation is interactive and read-only; the user can retry explicitly.

## Testing Strategy

Implementation will follow test-driven development.

### REST client tests

- rejects limits outside 1 through 50 before making a request;
- rejects unsupported review statuses before making a request;
- sends only a GET request to `/api/v1/inspections`;
- uses exactly one configured authentication scheme;
- includes the expected query parameters;
- returns only the approved inspection fields;
- rejects malformed JSON envelopes; and
- redacts credentials from transport and authorization failures.

### MCP registration tests

- imports the pinned `mcp-use` SDK;
- registers exactly one FreshSense business tool;
- exposes the expected name, description, and typed input schema;
- marks the tool read-only and non-destructive; and
- delegates tool calls to the tested REST client.

### Integration smoke test

- starts a local FreshSense test API with workspace-scoped data;
- starts or invokes the MCP server through the mcp-use client path;
- discovers `get_recent_inspections`;
- retrieves recent records for the authenticated workspace; and
- confirms that records belonging to another workspace are absent.

## Security and Privacy

This integration follows least privilege:

- one read-only tool;
- no direct database access;
- no photo access or retention;
- no mutation endpoints;
- no credentials in repository files or logs;
- existing FreshSense authentication and workspace isolation remain authoritative; and
- the MCP annotation communicates intent but is not treated as the security boundary. The REST API remains the enforcement layer.

## Non-Goals

This first integration will not:

- analyze or upload images;
- submit human reviews;
- create Agent tasks or notifications;
- approve or reject proposed actions;
- query the database directly;
- add an LLM or autonomous Agent to the MCP server;
- deploy a public unauthenticated MCP endpoint; or
- introduce billing, account administration, or partner-specific data models.

## Acceptance Criteria

The feature is complete when:

1. `mcp-use==1.7.0` is installed from an isolated dependency file.
2. A documented `get_recent_inspections` MCP tool can retrieve authenticated, workspace-scoped inspection metadata from the existing REST API.
3. The tool is declared read-only and exposes no mutation capability.
4. Invalid parameters, missing credentials, API failures, and malformed responses fail safely without leaking secrets.
5. Unit and integration tests prove tool discovery, tool invocation, authentication forwarding, field minimization, and workspace isolation.
6. A developer can reproduce the demo using the documented commands.
7. The Manufact application note includes one concrete sentence describing the implementation and a lesson learned from the SDK without implying a production deployment that did not occur.

