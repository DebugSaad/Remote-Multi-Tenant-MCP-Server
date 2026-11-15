# Technical Requirements Document (TRD)
## Remote Multi-Tenant MCP Server, Version 1

| | |
|---|---|
| **Status** | Draft |
| **Version** | 1.0 (v1 scope only) |
| **Owner** | Saad |
| **Related docs** | `PRD.md` (what and why), `architecture.md` (design and diagrams) |

This document says **how** v1 is built. Product goals and user stories are in the PRD. Component diagrams and flows are in `architecture.md`.

---

## 1. Technology Stack

| Need | Choice | Notes |
|---|---|---|
| Language | Python 3.12+ | Matches existing FastAPI experience |
| Web framework | FastAPI (async) | |
| MCP | Official MCP Python SDK, Streamable HTTP transport | Pin the version; check release notes before upgrading |
| Auth server | Keycloak (Docker) | Alternatives: Authentik, free-tier Auth0 or Clerk |
| Token validation | JWT verification with the auth server's JWKS | Library such as `PyJWT` or `authlib` |
| Database | PostgreSQL 16 | Row-level security |
| DB access | `asyncpg` or SQLAlchemy 2 (async) | Pick one and keep it consistent |
| Migrations | Alembic | |
| Cache and limits | Redis 7 | Lua script for the rate limiter |
| Validation | Pydantic v2 | |
| Metrics | `prometheus-client`, Prometheus, Grafana | |
| Logging | Structured JSON logs | |
| Testing | pytest, pytest-asyncio, httpx; Locust or k6 for load | |
| Packaging | Docker, Docker Compose | |
| CI | GitHub Actions | Free for public repos |

**Rule:** every service above has a free option. No LLM key is required.

---

## 2. Technical Scope

**In scope:** everything in PRD section 6.
**Out of scope:** reminders, files, teams, web UI, LLM calls from the server.

---

## 3. Authentication and Authorization

### 3.1 Requirements

| ID | Requirement |
|---|---|
| T-AUTH-1 | The server acts as an OAuth **resource server**. Login is delegated to the auth server. |
| T-AUTH-2 | Unauthenticated requests receive `401` with a `WWW-Authenticate` header pointing to the protected-resource metadata. |
| T-AUTH-3 | The server publishes protected-resource metadata at `/.well-known/oauth-protected-resource`, naming the auth server. |
| T-AUTH-4 | The auth server must support the authorization-code flow with **PKCE** and dynamic client registration. |
| T-AUTH-5 | Every access token is validated for: signature (JWKS, cached with refresh), `exp`, `nbf`, issuer, and **audience equal to this server's resource URL**. |
| T-AUTH-6 | The user identity is the token's `sub` claim. On first valid request, upsert a row in `users` and use its internal UUID as `user_id`. |
| T-AUTH-7 | Access tokens live about 5 to 15 minutes. Refresh tokens are handled by the client and auth server. |
| T-AUTH-8 | Admin role is read from a token claim or role. Admin endpoints reject non-admins with `403`. |
| T-AUTH-9 | Disabled users (`is_active = false`) are rejected even with a valid token. |
| T-AUTH-10 | Tokens are never logged. |

### 3.2 Notes

- The exact discovery and registration behavior comes from the current MCP authorization specification. **Re-read it before Phase 3**, as details evolve.
- Test with at least two clients (MCP Inspector and one real AI client).

---

## 4. MCP Gateway

### 4.1 Request pipeline

Every MCP request passes these steps in order:

1. Parse and size-check the request
2. Validate token (section 3)
3. Load user and check `is_active`
4. Rate-limit check (section 8)
5. Find or create session (section 9)
6. Dispatch to the tool
7. Write audit record
8. Return the result (stream if needed)

A failure at any step stops the pipeline and returns the mapped error (section 11).

### 4.2 Protocol support

| Message | Behavior |
|---|---|
| `initialize` | Create a session, return server info and capabilities |
| `tools/list` | Return the v1 tool definitions with input schemas |
| `tools/call` | Run the named tool with validated arguments |

### 4.3 Transport

- Single MCP endpoint (for example `POST /mcp`) using Streamable HTTP.
- Long-running responses stream as server-sent events with incrementing event IDs.
- Maximum request body size: 1 MB (configurable).

---

## 5. Tool Specifications

All tools receive a verified `user_id` from the gateway. **No tool accepts an owner or user ID as input.**

| Tool | Input fields and limits | Output |
|---|---|---|
| `create_note` | `title` (1 to 200 chars), `content` (0 to 10,000 chars) | `{ id }` |
| `list_notes` | `query` (optional, up to 100 chars), `limit` (1 to 100, default 20) | Array of `{ id, title, created_at }` |
| `get_note` | `id` (UUID) | `{ id, title, content, created_at, updated_at }` or not found |
| `delete_note` | `id` (UUID) | `{ deleted: true }` or not found |
| `add_task` | `title` (1 to 200 chars), `due_date` (optional ISO date) | `{ id }` |
| `list_tasks` | `status` (optional: `open` or `done`), `limit` (1 to 100) | Array of `{ id, title, due_date, status }` |
| `complete_task` | `id` (UUID) | `{ id, status: "done" }` or not found |
| `get_my_activity` | `limit` (1 to 50, default 20) | Array of `{ tool_name, status, duration_ms, created_at }` |

**Rules**

- Validate every input with Pydantic before touching the database.
- Treat stored text as plain data. Never execute or interpret it.
- Write tools are **idempotent where possible**: `delete_note` on a missing note returns not found, and `complete_task` on a done task returns done.
- Tool descriptions must be honest: `add_task` "tracks" tasks and does not remind.

---

## 6. Data Model

### 6.1 Schema

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  external_id text UNIQUE NOT NULL,          -- token "sub"
  email       text,
  role        text NOT NULL DEFAULT 'user',  -- 'user' or 'admin'
  is_active   boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE notes (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id   uuid NOT NULL REFERENCES users(id),
  title      text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
  content    text NOT NULL DEFAULT '' CHECK (char_length(content) <= 10000),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX notes_owner_idx ON notes (owner_id, created_at DESC);

CREATE TABLE tasks (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id   uuid NOT NULL REFERENCES users(id),
  title      text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
  due_date   date,
  status     text NOT NULL DEFAULT 'open' CHECK (status IN ('open','done')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX tasks_owner_idx ON tasks (owner_id, status);

CREATE TABLE audit_log (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id),
  tool_name   text NOT NULL,
  status      text NOT NULL,                 -- 'ok', 'error', 'rate_limited'
  duration_ms integer,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_user_idx ON audit_log (user_id, created_at DESC);
```

### 6.2 Row-level security

```sql
-- App connects as a normal role: no superuser, no BYPASSRLS.
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE notes FORCE ROW LEVEL SECURITY;

CREATE POLICY notes_owner ON notes
  USING      (owner_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
  WITH CHECK (owner_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);

-- Repeat for tasks (owner_id) and audit_log (user_id).
```

**Per request:** open a transaction and run `SET LOCAL app.current_user_id = '<uuid>'` (use `set_config('app.current_user_id', $1, true)` with a bound parameter, never string concatenation). If the setting is missing, the policy matches no rows.

**Admin reads** of other users' audit rows use a separate, explicit path (for example a dedicated admin DB role or policy). Do not weaken the user policies for this. Decide and document the approach in Phase 8.

### 6.3 Rules

- Repositories are the only code that writes SQL.
- Every repository function takes `user_id` as a required argument and filters on it, in addition to RLS.
- `audit_log` never stores note or task content.

---

## 7. Isolation Requirements

| ID | Requirement |
|---|---|
| T-ISO-1 | `user_id` comes only from the verified token. |
| T-ISO-2 | Every repository query filters by `owner_id` or `user_id`. |
| T-ISO-3 | RLS is enabled and **forced** on `notes`, `tasks`, and `audit_log`. |
| T-ISO-4 | The app's DB role cannot bypass RLS. A test verifies this. |
| T-ISO-5 | Accessing another user's record returns the same "not found" as a missing record. |
| T-ISO-6 | IDs are random UUIDs. |
| T-ISO-7 | An automated test suite attempts cross-user read, update, and delete for every tool and runs in CI. |
| T-ISO-8 | A test disables the application filter (RLS only) and confirms RLS alone blocks access. |

---

## 8. Rate Limiting

| Item | Specification |
|---|---|
| Algorithm | Token bucket per user |
| Storage | Redis key `rl:{user_id}` holding tokens and last-refill time |
| Atomicity | One Lua script does refill, check, and consume in a single call |
| Defaults | `RATE_LIMIT_BURST=20`, `RATE_LIMIT_PER_MINUTE=60` (configurable) |
| On limit | HTTP `429`, `Retry-After` header, structured error with seconds to wait |
| Audit | Rate-limited calls are recorded with status `rate_limited` |
| Key expiry | Idle keys expire (for example after 10 minutes) |
| Redis failure | Fail closed for write tools. Reads follow a documented policy. Decide and record this choice (open question in the PRD). |

**Pseudocode**

```
now = redis.time()
tokens, last = HMGET rl:{user}
tokens = min(burst, tokens + (now - last) * refill_rate)
if tokens >= 1: tokens -= 1; allow
else: deny, retry_after = (1 - tokens) / refill_rate
HSET rl:{user} tokens last=now; EXPIRE rl:{user} ttl
```

---

## 9. Sessions and Streaming

| ID | Requirement |
|---|---|
| T-SES-1 | `initialize` creates a session ID returned in the `Mcp-Session-Id` header. |
| T-SES-2 | Session state is stored in Redis at `session:{id}` with `user_id` and `last_seen`. |
| T-SES-3 | A session is valid only when the token's user matches the session's owner. A session ID alone grants nothing. |
| T-SES-4 | Sessions expire after a sliding timeout (default 30 minutes, `SESSION_TTL_SECONDS`). |
| T-SES-5 | Streamed events carry increasing IDs and are buffered at `events:{session_id}` with a capped length. |
| T-SES-6 | A reconnecting client sends `Last-Event-ID` and receives missed events from the buffer. |
| T-SES-7 | The server holds no session state in process memory, so any app copy can serve any session. |
| T-SES-8 | Closed or expired sessions are deleted, along with their event buffers. |

---

## 10. Audit and Observability

### 10.1 Audit

- One `audit_log` row per tool call: user, tool, status, duration, time.
- Written for success, error, and rate-limited outcomes.
- Never store tokens, secrets, or content.

### 10.2 Metrics (Prometheus)

| Metric | Type | Labels |
|---|---|---|
| `mcp_requests_total` | Counter | `tool`, `status` |
| `mcp_request_duration_seconds` | Histogram | `tool` |
| `mcp_rate_limited_total` | Counter | none |
| `mcp_auth_failures_total` | Counter | `reason` |
| `mcp_active_sessions` | Gauge | none |
| `mcp_db_pool_in_use` | Gauge | none |

**Do not label metrics by user ID** (high cardinality).

### 10.3 Health and logging

- `GET /health` returns status plus Postgres and Redis checks.
- `GET /metrics` is reachable from the internal network only.
- Logs are JSON with a request ID, user ID (internal UUID), tool, status, duration. No tokens or content.

---

## 11. Error Model

| Condition | HTTP status | Client-visible result |
|---|---|---|
| Missing, expired, forged, wrong-audience token | 401 | `WWW-Authenticate` header; no detail about why |
| User disabled | 403 | Generic "access denied" |
| Not an admin | 403 | Generic "access denied" |
| Rate limit exceeded | 429 | `Retry-After` seconds |
| Invalid input | 200 with tool error, or 400 for protocol errors | Message naming the invalid field |
| Record missing or not owned | 200 with tool error | "Not found" |
| Request too large | 413 | Size limit message |
| Unexpected failure | 500 | Generic error and request ID; details only in server logs |

Errors never reveal stack traces, SQL, or whether another user's record exists.

---

## 12. Configuration

All configuration is through environment variables. Provide `.env.example`. Never commit real values.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection (non-superuser role) |
| `REDIS_URL` | Redis connection |
| `AUTH_ISSUER_URL` | Expected token issuer |
| `AUTH_JWKS_URL` | Where to fetch signing keys |
| `MCP_RESOURCE_URL` | This server's public URL, used as the expected audience |
| `ADMIN_ROLE_NAME` | Role or claim value that marks an admin |
| `RATE_LIMIT_BURST` | Bucket size |
| `RATE_LIMIT_PER_MINUTE` | Refill rate |
| `SESSION_TTL_SECONDS` | Session sliding timeout |
| `MAX_REQUEST_BYTES` | Request size cap |
| `LOG_LEVEL` | Logging level |

---

## 13. Performance and Capacity Targets

| Metric | Target (confirm after first load test) |
|---|---|
| Typical tool-call latency (p95) | Under 300 ms |
| Rate-limit check | Under 10 ms |
| Concurrent users in load test | Choose a number (for example 50 to 200) and document results |
| Error rate under load | Under 1% excluding intended 429s |
| Isolation under load | Zero cross-user leaks |

Method: Locust or k6 with several users running mixed tool calls, with results and bottlenecks recorded in `docs/`.

---

## 14. Security Requirements

| ID | Requirement |
|---|---|
| T-SEC-1 | HTTPS only in any shared deployment. |
| T-SEC-2 | CORS limited to known origins. |
| T-SEC-3 | Secrets only in environment variables or a secrets manager. |
| T-SEC-4 | The app's DB role has least privilege and no bypass rights. |
| T-SEC-5 | Parameterized queries only. No string-built SQL. |
| T-SEC-6 | Input length and type limits on every tool. |
| T-SEC-7 | Request body size limit enforced at the gateway. |
| T-SEC-8 | Dependencies pinned, with automated vulnerability scanning in CI. |
| T-SEC-9 | Stored text is returned as data only and never treated as instructions. |
| T-SEC-10 | `/metrics` and admin endpoints are not publicly reachable. |

---

## 15. Testing Requirements

| Type | Must cover | Runs in CI |
|---|---|---|
| Unit | Each tool, validation, error mapping | Yes |
| Isolation | Cross-user read, update, delete for every tool; RLS-only test | Yes |
| Auth | Expired, forged, wrong-audience, wrong-issuer tokens; disabled user | Yes |
| Rate limit | Burst, refill, `Retry-After`, concurrent requests | Yes |
| Session | Create, expire, reconnect with `Last-Event-ID`, wrong-user session | Yes |
| Integration | Full flow with Postgres, Redis, and Keycloak in Docker | Yes |
| Load | Concurrent users, latency, error rate | Manual or scheduled |
| Manual | Real AI client end to end | Before release |

**Target:** every PRD acceptance criterion (AC-1 to AC-10) maps to at least one automated or documented manual test.

---

## 16. Deployment and Environments

| Environment | Setup |
|---|---|
| Local (primary) | `docker-compose.yml`: app, postgres, redis, keycloak, prometheus, grafana |
| CI | GitHub Actions with service containers for Postgres and Redis |
| Public demo (optional) | Free-tier host for the app, free-tier Postgres and Redis, tunnel for HTTPS |

**Known limits:** free tiers can sleep, cap connections, and restrict storage. Document them in the README.

**Release steps:** run migrations, start the app, check `/health`, run the smoke test.

---

## 17. Implementation Plan

This matches the Version 1 Task List.

| Phase | Focus | Key technical output |
|---|---|---|
| 0 | Setup | Repo, Compose file, design notes |
| 1 | Basic MCP server | Hello-world tool over HTTP, `/health` |
| 2 | Database and tools | Schema, migrations, all tools with a test user |
| 3 | Authentication | Keycloak, metadata, token validation, real user ID |
| 4 | Isolation | Filters, RLS, isolation test suite |
| 5 | Rate limiting | Redis token bucket, 429 handling |
| 6 | Sessions and streaming | Session store, event buffer, resume |
| 7 | Audit and observability | Audit writes, `get_my_activity`, metrics, dashboard |
| 8 | Admin | User list, disable, revoke |
| 9 | Test and polish | Full tests, load test, README, demo |

---

## 18. Technical Risks

| Risk | Mitigation |
|---|---|
| OAuth and discovery differ between clients | Use Keycloak; follow the current spec; test two or more clients |
| RLS not applied because the DB role bypasses it | Test T-ISO-4; use a non-superuser role and `FORCE ROW LEVEL SECURITY` |
| Connection pool leaks the current-user setting between requests | Use `SET LOCAL` inside a transaction only; test for leakage |
| Race conditions in the rate limiter | Single atomic Lua script; concurrent tests |
| Event buffer grows without bound | Cap length and set expiry |
| JWKS fetch failure blocks all requests | Cache keys with a refresh and a short grace period |

---

## 19. Open Technical Questions

1. Which DB access library: `asyncpg` directly or SQLAlchemy async?
2. Exact admin approach for reading all audit rows (separate role or policy)?
3. Redis outage policy for read tools?
4. Final rate-limit numbers and session timeout?
5. Target number of concurrent users for the load test?
6. Public demo host and tunnel choice?
