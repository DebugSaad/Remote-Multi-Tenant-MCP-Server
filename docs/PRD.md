# Product Requirements Document (PRD)
## Remote Multi-Tenant MCP Server, Version 1

| | |
|---|---|
| **Status** | Draft |
| **Version** | 1.0 (v1 scope only) |
| **Owner** | Saad |
| **Related docs** | `architecture.md`, `TRD.md`, `ROADMAP.md` |

---

## 1. Summary

AI assistants such as Claude can use **tools** through a standard called MCP (Model Context Protocol). Most MCP servers run on one person's computer. This product is a **hosted MCP server on the internet that many people share safely**: each person logs in, works with their own private data, and cannot see anyone else's. The server also limits usage per person and records every action.

**Analogy:** one company library with membership cards. One building, many members, each with a private locker, a visit limit, and a logbook at the door.

---

## 2. Problem

Companies and teams want everyone to use AI assistants with shared internal tools. Local MCP servers make that hard:

| Problem | Impact |
|---|---|
| Every person installs and configures their own server | Slow rollout, non-technical users are excluded |
| Passwords and API keys are copied to many laptops | Security risk |
| No central record of what AI tools do | No accountability or compliance |
| No standard guarantee that user A cannot see user B's data | Data leak risk |
| Nothing stops one heavy user from overloading the system | Unfair performance |
| Different people run different versions | Inconsistent behavior |

There is no simple, secure, ready-made pattern for a **multi-user remote MCP server**. This product provides one.

---

## 3. Goals and Non-Goals

### Goals (v1)

1. Let many users connect to one hosted server with a link and a login.
2. Guarantee and prove that each user's data is isolated.
3. Apply fair per-user usage limits.
4. Keep connections reliable, with streaming and resumable sessions.
5. Record an audit trail of every tool call.
6. Run the whole project on free tools.

### Non-goals (v1)

- Task reminders and notifications (v2)
- File storage, teams, shared notes (v2)
- A web interface for browsing notes (v2)
- Calling an LLM from the server (the server is LLM-agnostic and needs no AI API key)
- Billing or payments

---

## 4. Users

| Persona | Description | Needs |
|---|---|---|
| **End user** (Ali, Sara) | Person using an AI assistant for notes and tasks | Easy connection, private data, reliable results |
| **AI client** | Claude, Cursor, or a custom agent acting for the user | A standards-compliant server with working login and tool discovery |
| **Admin** | Project owner or IT person | See usage, disable abusive users, revoke access |
| **Reviewer** (secondary) | Recruiter or engineer reading the project | Clear docs, proof of isolation, a short demo |

---

## 5. User Stories

**End user**
- As a user, I connect my AI assistant by adding one link and signing in.
- As a user, I tell my assistant to save a note, and it is stored under my account.
- As a user, I ask for my notes or tasks and see only mine.
- As a user, I add tasks with an optional due date and mark them done.
- As a user, I see a history of my recent tool calls.
- As a user, if I send too many requests, I get a clear message telling me when to retry.

**AI client**
- As a client, I discover the login location automatically and register myself.
- As a client, I refresh my token without asking the user to sign in again.
- As a client, I resume a stream after a dropped connection.

**Admin**
- As an admin, I list users and their usage.
- As an admin, I disable a user and revoke their tokens.

---

## 6. Scope: What v1 Includes

| Area | Feature |
|---|---|
| Login | OAuth 2.1 with PKCE through an existing auth server |
| Protocol | MCP over HTTP: initialize, tool discovery, tool calls |
| Tools | Notes (create, list, get, delete), Tasks (add, list, complete), Activity (view own history) |
| Isolation | Per-user data separation in the app and in the database |
| Limits | Per-user rate limiting with a retry time |
| Sessions | Session tracking and resume after disconnect |
| Streaming | Streamed results for long-running calls |
| Audit | A record of every tool call |
| Admin | List users and usage, disable user, revoke tokens |
| Observability | Health check, metrics, dashboard |

---

## 7. Functional Requirements

Priority: **P0** = must have for v1, **P1** = should have, **P2** = nice to have.

### Authentication

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Users log in through OAuth 2.1 with PKCE | P0 |
| FR-2 | MCP clients can register themselves and obtain access tokens | P0 |
| FR-3 | Tokens expire, can be refreshed, and can be revoked | P0 |
| FR-4 | Every request is tied to a verified user | P0 |

### MCP protocol

| ID | Requirement | Priority |
|---|---|---|
| FR-5 | The server supports the MCP handshake and tool discovery | P0 |
| FR-6 | The server executes tool calls over HTTP | P0 |
| FR-7 | The server streams results for long-running tools | P1 |
| FR-8 | The server returns clear, structured errors | P0 |

### Tools

| ID | Requirement | Priority |
|---|---|---|
| FR-9 | Users can create, list, read, and delete notes | P0 |
| FR-10 | Users can add, list, and complete tasks, each with an optional due date | P0 |
| FR-11 | Users can view their own recent activity | P1 |

### Isolation

| ID | Requirement | Priority |
|---|---|---|
| FR-12 | Every record belongs to exactly one user | P0 |
| FR-13 | A user can never read, change, or delete another user's data | P0 |

### Limits and sessions

| ID | Requirement | Priority |
|---|---|---|
| FR-14 | Per-user rate limits apply to all tool calls | P0 |
| FR-15 | Rate-limited requests receive a clear message with a retry time | P0 |
| FR-16 | Sessions can be resumed after a dropped connection | P1 |

### Audit and admin

| ID | Requirement | Priority |
|---|---|---|
| FR-17 | Every tool call is written to the audit log | P0 |
| FR-18 | Admins can view users and usage | P1 |
| FR-19 | Admins can disable a user and revoke their tokens | P1 |
| FR-20 | A health-check endpoint reports server status | P0 |

---

## 8. Non-Functional Requirements (Summary)

| Area | Requirement |
|---|---|
| Security | HTTPS only, token checked on every call, two-layer data isolation, no secrets in logs |
| Performance | Typical tool call under 300 ms at normal load |
| Scalability | Stateless app copies, shared state in Redis and PostgreSQL |
| Reliability | No duplicate writes on retries; sessions survive dropped connections |
| Privacy | Users see only their own data; logs hold no note content |
| Compatibility | Works with any standards-compliant MCP client |
| Cost | $0 using free tools and free tiers |

Detailed targets and implementation are in `TRD.md`.

---

## 9. User Experience

There is **no custom screen in v1**. The AI assistant's chat window is the interface.

**Typical journey**

1. The user adds the server link to their AI client.
2. The client opens a login page. The user signs in and approves access, once.
3. The user says: *"Save a note: client meeting on Monday."*
4. The assistant calls `create_note`. The server stores it under the user's account.
5. Later the user says: *"Show my notes."* The assistant calls `list_notes` and shows only that user's notes.

**Messages the user may see**

| Situation | What the user experiences |
|---|---|
| Not logged in | The client asks them to sign in |
| Too many requests | A message saying to retry in N seconds |
| Asking for a note that is not theirs or does not exist | "Not found" |
| Invalid input (for example, a title that is too long) | A clear message saying what to fix |

**Reminder behavior:** `add_task` stores a due date only. v1 does **not** send reminders. Documentation and tool descriptions must say "tracks tasks", not "reminds".

---

## 9.1 Tool Catalog

| Tool | Purpose | Inputs |
|---|---|---|
| `create_note` | Save a note | title, content |
| `list_notes` | List the user's notes | optional search text |
| `get_note` | Read one note | note ID |
| `delete_note` | Delete one note | note ID |
| `add_task` | Add a task | title, optional due date |
| `list_tasks` | List the user's tasks | optional status |
| `complete_task` | Mark a task done | task ID |
| `get_my_activity` | See own recent tool calls | optional limit |

---

## 10. Acceptance Criteria

| # | Given / When / Then |
|---|---|
| AC-1 | **Given** two users are logged in, **when** each saves a note and lists notes, **then** each sees only their own. |
| AC-2 | **Given** user A knows the ID of user B's note, **when** A tries to get, change, or delete it, **then** the server returns "not found" and nothing changes. |
| AC-3 | **Given** a request with an expired, forged, or wrong-audience token, **when** it is sent, **then** the server returns 401 and runs no tool. |
| AC-4 | **Given** a user exceeds the rate limit, **when** they send another call, **then** they receive 429 with a retry time, and can call again after the time passes. |
| AC-5 | **Given** a stream is interrupted, **when** the client reconnects, **then** it resumes without losing the result. |
| AC-6 | **Given** any tool call completes or fails, **then** an audit record exists with user, tool, status, and duration. |
| AC-7 | **Given** an admin disables a user, **when** that user calls any tool, **then** the call is rejected. |
| AC-8 | **Given** a client without a token, **when** it connects, **then** it can discover the login location and finish the login. |
| AC-9 | **Given** a load test with many simultaneous users, **then** isolation tests still pass and results are documented. |
| AC-10 | **Given** a new person follows the README, **then** they can run the project locally and complete the demo script. |

---

## 11. Success Metrics

| Metric | Target |
|---|---|
| Isolation tests passing | 100%, run automatically |
| Cross-user data leaks found in testing | 0 |
| p95 tool-call latency under load test | Under 300 ms at the tested user count (set the count after a first load test) |
| Rate-limit accuracy | Blocked requests return 429 with a correct retry time in tests |
| Audit coverage | 100% of tool calls recorded |
| Demo | A 5-minute demo runs end to end |
| Cost | $0 |

---

## 12. Assumptions and Dependencies

- Users have an AI client that supports remote MCP servers with OAuth.
- An existing auth server (Keycloak or similar) handles login. A custom one is not built.
- Free tiers and local Docker are enough for development and the demo.
- The MCP authorization specification may change, so it must be re-checked before building login.
- No LLM key is needed, because the AI client brings its own.

---

## 13. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| OAuth for MCP is complex and clients behave differently | High | High | Use an existing auth server; test with several clients; budget extra time |
| A missed filter leaks data | Medium | High | Row-level security plus automated isolation tests |
| Streaming and resume bugs | Medium | Medium | Redis event buffer; explicit disconnect tests |
| Free hosting sleeps or limits connections | High | Low | Document limits; demo locally if needed |
| Scope creep | High | Medium | Hold to this scope and `ROADMAP.md` |
| Prompt injection through stored notes | Medium | Medium | Tools return data only; v1 tools touch only the caller's own data |

---

## 14. Milestones

These map to the phases in the Version 1 Task List.

| Milestone | Phases | Outcome |
|---|---|---|
| M1: Working tools | 0 to 2 | MCP server with all tools and a database, using a test user |
| M2: Secure access | 3 to 4 | Real login and proven data isolation |
| M3: Fair and reliable | 5 to 6 | Rate limiting, sessions, streaming |
| M4: Observable | 7 to 8 | Audit log, metrics, dashboard, admin |
| M5: Ship | 9 | Tests, load test, README, demo |

---

## 15. Out of Scope: Planned for v2

- Task reminders with a scheduler and a notification channel
- A web page where users browse and edit notes
- File storage tool
- Teams, shared notes, and roles
- Plugin-style tool registration

---

## 16. Open Questions

1. Which auth server will be used: Keycloak or a free-tier provider?
2. What are the final rate-limit numbers per user?
3. If Redis fails, should the server block all calls or only writes?
4. How many concurrent users should the load test target?
5. Will there be a public demo, or local only?
