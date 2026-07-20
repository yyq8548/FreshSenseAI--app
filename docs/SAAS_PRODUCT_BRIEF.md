# FreshSense 0.6 SaaS Product Brief

## Product goal

FreshSense is being developed into an AI-assisted produce inspection platform
for small grocery stores and produce teams. Staff can record visible fruit
condition, receive bounded model guidance, and submit a human review that makes
the outcome auditable.

FreshSense is decision support. It is not a food-safety test, an autonomous
quality-control system, or evidence that a product is safe to sell or consume.

## Initial users

- Produce associates checking a delivery or shelf item.
- Produce managers reviewing uncertain or corrected results.
- Pilot owners measuring adoption, model errors, and workflow completion.

The first release targets one controlled pilot workflow. It does not attempt to
serve every grocery operation or replace established receiving procedures.

## Core workflow

1. An authenticated staff member selects a store or receiving location.
2. The staff member photographs one supported fruit type and optionally enters
   a batch reference.
3. FreshSense validates the input, runs supported-input and freshness models,
   retrieves relevant guidance, and returns warnings.
4. The service discards the uploaded image and filename after the request.
5. FreshSense stores only the analysis metadata inside the authenticated
   workspace.
6. A staff member confirms, corrects, or dismisses the result and may record an
   operational note.
7. The dashboard summarizes actual inspection and review records without
   inventing accuracy or business-impact metrics.

## First SaaS release boundary

FreshSense 0.6 consists of two increments.

### Implemented foundation

- Workspace-scoped inspection metadata.
- Location and optional batch context.
- Existing model analysis reused through FastAPI.
- Human confirmation, correction, and dismissal.
- Append-only review events for auditability.
- Review completion, decision, fruit, and false-fresh review counts.
- Microsoft Entra External ID access-token validation using OIDC discovery and
  rotating signing keys.
- Email-bound, one-time workspace invitations with hashed token storage.
- Manager, inspector, and reviewer authorization at API action boundaries.
- Responsive Microsoft Fluent UI workbench using only authenticated API data.
- API-key identity isolation remains available for controlled local testing.
- No uploaded image or filename retention.

### Required before a public hosted beta

- Azure Database for PostgreSQL migration and managed backups.
- Durable distributed rate limits and per-plan usage quotas.
- Azure Key Vault, managed identity, Application Insights, and alerting.
- Terms, privacy controls, account deletion, and support workflow.
- Staging deployment, load tests, security review, and rollback procedure.

API-key authentication is not presented as customer login. Entra mode is the
customer-facing authentication boundary. The product is still a local staging
system until its Entra registrations, web client, API, and database are deployed
and independently reviewed.

## Data policy

The default policy is metadata only.

Stored:

- workspace and location identifiers;
- optional user-entered batch reference and note;
- model decision, accepted prediction, confidence, warnings, and version;
- human review outcome, note, status, and timestamps.

Not stored:

- uploaded image bytes;
- uploaded filename;
- Grad-CAM image unless a future user explicitly exports it;
- biometric or payment data.

Any future photo retention must be opt-in, time-bounded, access-controlled, and
documented separately.

## Pilot success measures

- Percentage of inspections receiving a human review.
- Median time from inspection to review.
- Unsupported and uncertain input rates.
- False-fresh and false-rotten corrections.
- Error patterns by fruit, lighting, device, and location when reviewed data is
  available.
- User comprehension of the result and safety warning.

These measures must come from recorded observations. Informal feedback and
legacy test accuracy cannot be substituted for them.

## Product decisions

- Start with apples, bananas, and oranges rather than expanding the catalog.
- Prioritize workflow reliability, review evidence, and orange failure analysis.
- Keep the Windows application available as an offline companion.
- Deploy Python/FastAPI directly to Azure App Service without requiring Docker.
- Delay billing until a controlled pilot demonstrates repeat use and a clear
  buyer.
