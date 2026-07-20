# FreshSense Manager Chat

## Purpose

Manager Chat lets a store manager ask follow-up questions about inspection
history, batch references, Agent decisions, open review work, and pending
approvals. It is a workspace assistant, not a general food-safety chatbot and
not an alternate path for executing operational actions.

## Implemented flow

1. The API verifies the signed-in user and requires the `manager` workspace
   role.
2. The manager's message is stored in a workspace-scoped conversation.
3. FreshSense combines the latest conversation turns so short follow-ups such as
   "why?" retain the earlier batch or fruit context.
4. The service reads relevant inspections, audited Agent runs, open tasks,
   pending approvals, manager preferences, and reviewed food knowledge.
5. If OpenAI reasoning is configured, the Responses API generates an answer from
   that bounded evidence. API-side response storage is disabled.
6. If the provider is disabled, unavailable, or returns an invalid response,
   FreshSense writes a deterministic grounded summary instead.
7. The answer and its source references are stored so the conversation survives
   page refreshes and later sessions.

The chat payload never includes uploaded photo bytes, filenames, credentials,
identity hashes, or data from another workspace.

## Memory and preferences

Schema version 5 adds three tables:

- `manager_conversations` stores title, status, owner workspace, and timestamps;
- `manager_messages` stores user and assistant text, source references, public
  provenance metadata, and timestamps;
- `manager_preferences` stores per-manager language, response detail, default
  store location, review focus, and optional instructions.

Conversation memory is managed by FreshSense rather than relying on a provider
conversation ID. This keeps tenant checks and retention behavior inside the
application. Conversations are private to their creating manager even when a
workspace has multiple managers. The model receives only the last bounded set
of turns plus the evidence needed for the current question.

## Safety and authority

Manager Chat can explain records and propose a next step. It cannot:

- approve or reject a batch hold;
- discard inventory;
- declare produce safe to eat;
- alter an inspection or human review;
- call an external inventory system; or
- access another workspace's records.

High-risk actions remain in the existing approval API and require an explicit
manager decision after a physical check. Every assistant message records whether
OpenAI or the grounded fallback produced it and always records
`actions_executed: false`.

## API surface

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/manager/preferences` | Read personal assistant preferences |
| `PATCH` | `/api/v1/manager/preferences` | Update validated preferences |
| `GET` | `/api/v1/manager/conversations` | List active conversations |
| `POST` | `/api/v1/manager/conversations` | Create a conversation |
| `GET` | `/api/v1/manager/conversations/{id}` | Read messages and citations |
| `POST` | `/api/v1/manager/conversations/{id}/messages` | Ask a grounded follow-up question |
| `POST` | `/api/v1/manager/conversations/{id}/archive` | Archive a conversation |

## Validation

The automated tests cover:

- multi-turn history persistence;
- manager preference validation;
- workspace isolation;
- inspection and knowledge citations;
- provider failure fallback;
- explicit no-action provenance;
- authenticated REST and OpenAPI contracts; and
- frontend message validation and provenance labels.

The versioned `manager_chat_v1` evaluation now covers batch facts, required
citations, multi-turn context, Chinese preferences, provider fallback,
cross-workspace prompt injection, high-risk action boundaries, and latency. Its
deterministic fallback quality gate runs in CI and publishes a report artifact.

Before broader use, run the same manifest against the configured OpenAI model
and have human reviewers score factual correctness, source support, usefulness,
and authority boundaries. See [MANAGER_CHAT_EVALUATION.md](MANAGER_CHAT_EVALUATION.md).
