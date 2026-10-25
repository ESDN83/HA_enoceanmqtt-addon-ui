# 0033. AI assistants get a setup guide from the app itself

Status: proposed (v1.8.5-beta9).

## Context

Users ask AI assistants to help set up EnOcean devices. The assistants reach
Home Assistant through an MCP server: HA's own `mcp_server` integration
(entities and Assist only) or an extended one such as ha-mcp. What we learned
from real devices (Eltako learn counts, valves that only listen after they
send, pilot wire queries, shared sender IDs) is in DOCS.md and the ADRs, which
no assistant reads. A model's general EnOcean knowledge gets these devices
wrong.

Constraints: nothing may depend on the user installing or approving another
MCP connection per client, and nothing goes into other projects' repos.

Checked on the devcontainer with ha-mcp:

- `ha_get_addon` shows the add-on's `description` from config.yaml, not
  DOCS.md (`documentation: true` only).
- `ha_manage_addon` in proxy mode calls any add-on endpoint through Ingress
  (GET, POST, PUT, DELETE), e.g. `/openapi.json`, and marks the answer as
  third-party data.

## Decision

- `GET /api/ai/guide` serves `data/ai_guide.md`: ground rules (ask before
  writes, never delete devices), the endpoints to use, the add-device and
  teach-in flows, per-family pitfalls, migration and diagnosis. It is
  maintained by hand next to DOCS.md, short enough for one tool call.
- The two places an assistant sees first point to it: the config.yaml
  `description` and the OpenAPI `info.description`.
- `llms.txt` at the repo root points to the same file for assistants that
  read the repository.
- The guide is data for the assistant, not instructions it must follow; the
  rules in it only restate what the app already enforces or what the user
  decides.

## Consequences

- Works today with ha-mcp and any MCP server that can reach add-on APIs,
  without installing anything.
- HA's default `mcp_server` cannot reach add-on APIs. Reaching it would need
  an LLM API registered in HA (one confirmation in HA) or knowledge carried
  in entities; that is a separate decision.
- The guide is part of the development pipeline: every change to device
  behaviour, teach-in, entities, endpoints, migration or debugging updates it
  together with DOCS.md (CLAUDE.md conventions). CI
  (`.github/scripts/check_ai_guide.py`) fails when the guide names an
  endpoint the app does not have.
