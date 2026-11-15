# Open Technical Questions: Answers

Answers to the six open questions in section 19 of `TRD.md`, for version 1 of the Remote Multi-Tenant MCP Server.

| # | Question | Decision |
|---|---|---|
| 1 | Database access library | SQLAlchemy 2 async with the `asyncpg` driver, using Core or `text()` queries |
| 2 | Admin access to all audit rows | A separate database role, `app_admin`, with a narrow policy |
| 3 | Redis outage policy | Reads fail open with a local limiter; writes and admin fail closed |
| 4 | Rate limits and timeouts | Burst 20, 60 per minute, writes cost 2, session 30 min sliding |
| 5 | Load-test size | 50 concurrent users, with a 100-user stress step |
| 6 | Public demo hosting | Run locally with Docker Compose and expose it with a tunnel |

---

## 1. Database access library

**Decision:** SQLAlchemy 2 async, using `asyncpg` as the driver. Write queries with Core or `text()`, not the full ORM.

| | `asyncpg` directly | SQLAlchemy async |
|---|---|---|
| Learning curve | Low (plain SQL) | Medium |
| Control over SQL and RLS | Full | Full, if using Core or `text()` |
| Raw speed | Slightly faster | Slightly slower, not noticeable here |
| Migrations | Alembic works, but SQL is hand-written | Alembic fits naturally |
| Pooling and transactions | Managed by you | Built in |
| Testing fixtures | More manual | Easier (sessions and rollbacks) |

**Why**

- Alembic is built for SQLAlchemy, and the project has several migrations (tables, indexes, RLS policies).
- Isolation depends on one transaction per request, so a clean transaction pattern matters.
- The isolation test suite needs many users and rollbacks, which sessions make easier.
- Using Core or `text()` keeps full control of the SQL and RLS without ORM complexity.

**Rule to follow**

- Set the current user with `set_config('app.current_user_id', :id, true)` inside the transaction. The `true` makes it transaction-local, so a pooled connection cannot carry one user's ID into the next request.

**Tests to add**

- Run two requests on the same pooled connection and confirm the second sees nothing from the first.

**Decision record:** "SQLAlchemy 2 async with asyncpg, Core queries, for Alembic and test fixtures."

---

## 2. Admin access to all audit rows

**Decision:** a separate database role, `app_admin`, with its own read-only policy. No session flag, no `BYPASSRLS`.

| Option | How it works | Problem |
|---|---|---|
| A. Policy on a session setting | Policy allows all rows when `app.is_admin = 'true'` | The app sets the value, so one bug or injection that sets it exposes every user's audit rows |
| **B. Separate DB role (chosen)** | `app_admin` has its own policy and connection | Slightly more setup |
| C. `SECURITY DEFINER` function | A function with owner rights returns audit rows | Powerful, easy to misuse, harder to test |

**Why B**

- The database enforces it. Normal request connections use `app_user`, which cannot read other users' rows whatever the app code does.
- Small blast radius: `app_admin` gets `SELECT` on `audit_log` and `users`, plus `UPDATE` on `users.is_active` for disabling users.
- `BYPASSRLS` is too broad. A narrow policy for one role is enough.

**Sketch**

```sql
CREATE ROLE app_admin LOGIN PASSWORD '...';   -- no BYPASSRLS
GRANT SELECT ON audit_log, users TO app_admin;
GRANT UPDATE (is_active) ON users TO app_admin;

CREATE POLICY audit_admin_read ON audit_log
  FOR SELECT TO app_admin USING (true);
```

**How the app uses it**

- A second connection pool built from `ADMIN_DATABASE_URL`, used only by the `admin` module, kept small (2 to 3 connections).
- Admin endpoints check the admin role in the token first, and only then use the admin pool.

**Tests to add**

- `app_user` cannot read another user's audit rows, even without the application filter.
- `app_admin` can read all audit rows but cannot read or write `notes` or `tasks`.
- A non-admin token calling `/admin/...` gets `403` and never opens the admin pool.

**Related requirement:** when an admin disables a user, that user's existing token must stop working right away. Check `is_active` on every request, and revoke the user's sessions and tokens at the auth server.

**Decision record:** "Admin audit access uses a dedicated `app_admin` DB role with a narrow SELECT policy; no session flag, no BYPASSRLS."

---

## 3. Redis outage policy for read tools

**Decision:** reads fail open with a stricter local limiter. Writes and admin endpoints fail closed.

| Policy | Problem |
|---|---|
| Block everything | One Redis failure takes the whole service down |
| Allow everything, no limits | An abuser can overload Postgres while Redis is down |
| **Reads open with a fallback, writes closed (chosen)** | Slightly more code, but degrades gracefully |

**Behavior when Redis is down**

| Area | Behavior |
|---|---|
| Read tools (`list_notes`, `get_note`, `list_tasks`, `get_my_activity`) | Allowed, using an in-memory limiter per app copy at half the normal rate |
| Write tools (`create_note`, `delete_note`, `add_task`, `complete_task`) | Rejected with `503` and a short retry hint |
| Sessions | Not required for reads, because the token already proves identity |
| Streaming resume | Unavailable. Clients get a clean error and start a new call |
| Admin endpoints | Fail closed |
| `/health` | Reports `degraded`, not `down` |

**Why writes fail closed**

- Writes change data, so an unlimited flood is the real danger.
- Users can retry a rejected write. They cannot undo a runaway one.

**Implementation points**

- Short timeouts (about 50 to 100 ms) on Redis calls, so an outage does not add seconds of latency.
- A circuit breaker: after a few failures, skip Redis for a few seconds, then retry.
- A metric such as `mcp_redis_degraded` (0 or 1), with an alert.
- Record the outage state in logs so behavior can be explained later.

**Known limitation**

- With several app copies, each local limiter sees only its own traffic, so the effective per-user limit multiplies by the number of copies during an outage. Accept this for v1, or divide the fallback rate by the number of copies.

**Tests to add**

- Stop the Redis container: reads work, writes return `503`, `/health` shows `degraded`.
- Restart Redis: normal behavior returns without restarting the app.
- Hammer a read tool during the outage: the local limiter still blocks it.

**Decision record:** "Redis outage: reads fail open with a local limiter, writes fail closed, admin fails closed."

---

## 4. Rate-limit numbers and session timeouts

**Decision:** start with these values and tune after the first load test. All are environment variables.

### Rate limits (per user)

| Setting | Value | Why |
|---|---|---|
| `RATE_LIMIT_BURST` | 20 | Covers an AI agent chaining several tool calls |
| `RATE_LIMIT_PER_MINUTE` | 60 | One call per second sustained, plenty for a person using an assistant |
| Write tool cost | 2 tokens per call | Writes are riskier, so they drain the bucket faster, with no second limiter to build |
| Redis-outage fallback (reads) | Burst 10, 30 per minute | Half the normal rate, per app copy |
| `MAX_REQUEST_BYTES` | 1 MB | Notes are capped at 10,000 characters, so this is generous |

### Session and token timeouts

| Setting | Value | Why |
|---|---|---|
| `SESSION_TTL_SECONDS` | 1800 (30 min), sliding | Resets on every call, so active users are not cut off |
| Absolute session limit | 8 hours | Forces a fresh session even on very long connections |
| Access token lifetime | 10 minutes | Short, so a stolen token expires quickly |
| Refresh token (Keycloak) | Idle 30 min, max 10 hours | The client refreshes silently |
| Stream event buffer | Last 100 events or 5 minutes, whichever is smaller | Enough for a quick reconnect without growing Redis |
| Max sessions per user | 5 | Stops one user from creating thousands of sessions |

### How they fit together

- The session timeout (30 min) should not exceed the refresh-token idle timeout (30 min). If the refresh token expires first, the user must log in again anyway.
- The access token (10 min) is shorter than the session (30 min), so the client refreshes several times per session. That is normal and exercises the refresh logic.

### Tuning after the load test

- If real users hit `429` in normal use, raise the burst first, then the per-minute rate.
- If Redis memory grows, shorten the session TTL and the event buffer.
- If abuse appears, raise the write cost from 2 to 3 tokens.

**Worked example:** burst 20 with a refill of 1 token per second. A user who spends the whole bucket on writes (2 tokens each) makes 10 writes, then needs 20 seconds to afford 10 more.

**Decision record:** "Defaults: burst 20, 60 per minute, writes cost 2, session 30 min sliding, access token 10 min."

**Update needed in TRD section 8:** add the write cost of 2 tokens and the fallback numbers above.

---

## 5. Load-test target

**Decision:** 50 concurrent users as the main target. Ramp 10, 25, then 50, and add a 100-user stress step to find the breaking point.

**Why 50**

- It is realistic for a small team.
- A laptop can run it with Docker for free.

**Two kinds of simulated users**

| Type | Behavior | Purpose |
|---|---|---|
| Polite users | 1 to 3 seconds between calls, under the rate limit | Measure latency and error rate |
| One abusive user | Sends calls as fast as possible | Prove the limiter returns `429` and other users stay fast |

**Also run isolation checks under load**

- Users A and B repeatedly try to read each other's note IDs. Every attempt must fail.

**What to record**

- p95 latency, error rate (excluding intended `429`s), Postgres connections in use, Redis memory.

**Tool:** Locust.

**Pass line:** p95 under 300 ms at 50 users, with zero cross-user leaks. If the target is missed, document the bottleneck.

**Decision record:** "Load test: 50 concurrent users, stress step at 100; polite and abusive user mix; isolation checks included."

---

## 6. Public demo host and tunnel

**Decision:** run the full stack locally with Docker Compose and expose it with a tunnel. Treat a free host as an optional extra.

**Why not a free host (hosting details checked in September 2026; re-check before relying on them)**

- Render's free web service sleeps after 15 idle minutes and takes about a minute to wake, which would break sessions and streams.
- Free tiers have shrunk. Fly.io has no monthly free allowance anymore, and Railway gives only a small trial credit and then about $1 a month.
- A free web service gets 512 MB of RAM and less than one CPU. As far as I know, Keycloak alone usually wants about 1 GB, so the full stack will not fit.
- Free hosted databases expire. Render's free Postgres lasts 30 days, according to one comparison.

**Plan**

| Part | Choice |
|---|---|
| App, Postgres, Redis, Keycloak, Grafana | Docker Compose on your laptop |
| Public HTTPS URL | Cloudflare Tunnel or ngrok |
| Audience | Interviewers and friends during live demos |
| Fallback | A 3-minute screen recording and the demo script in the README |

**Things to handle**

- Set `MCP_RESOURCE_URL` and the Keycloak issuer to the tunnel's public URL, or token validation fails.
- Use a named tunnel hostname if possible. Quick tunnels get a new random URL on every run, and clients register against the old one.
- If the URL changes between demos, update the audience and issuer settings and re-register the client. Otherwise tokens are rejected for a wrong audience or issuer.
- Expose only `/mcp` and the discovery endpoints through the tunnel. Keep admin and `/metrics` private.
- The laptop must be on. State in the README: "Demo available on request."

**Optional later:** deploy only the app and a free managed Postgres to a free host, with a hosted auth provider (Auth0 or Clerk free tier) in place of Keycloak. This is a second deployment path, so skip it in v1.

**Decision record:** "Demo: local Docker Compose plus Cloudflare Tunnel or ngrok; free PaaS deployment is optional and later."

---

## Follow-up Edits

- [ ] `TRD.md` section 19: mark all six questions as answered and link this file
- [ ] `TRD.md` section 8: add the write cost of 2 tokens, the Redis outage behavior, and the fallback rate
- [ ] `TRD.md` section 6.2: replace the admin note with the `app_admin` role approach
- [ ] `PRD.md` section 16: close open questions 2, 3, 4, and 5
- [ ] `docs/decisions/`: add one line per decision record above
- [ ] `.env.example`: add `ADMIN_DATABASE_URL` and the rate-limit and session values from section 4
