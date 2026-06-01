# M3 Tier 1 — Supabase

Plugs Lifeline into the cloud for sync across devices/users and (later) the web chats.
**No Redis** (decision #0038): Postgres = store, Auth = OAuth, RLS = tenant, Realtime = push.

> Status: **adapter promoted to the package (`lifeline/cloud.py`) and covered by mocked
> transport tests** (`tests/test_supabase.py`). The **real contract** (schema/RLS/PostgREST)
> is proven by the **skip-gated live test** — which runs when `SUPABASE_URL`/`KEY` are in the
> environment. Until that test passes against a project, treat it as *"wired, not validated live"*.

Project: `https://rzphncyjrilhwpuemrcl.supabase.co` (ref `rzphncyjrilhwpuemrcl`).

## Security (read first)

- **Never** paste the `service_role` key or the database password into chat or a commit.
- The schema step (below) runs **in your Dashboard** — it does not require sharing any key.
- The runtime reads from the **environment** (`SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_TOKEN`); use a
  `.env` (already in `.gitignore`).

## Auth — decision (important)

The Supabase gateway requires **TWO distinct values** (validated live, #0042 — using the JWT
as `apikey` gives `401 Invalid API key`):

- **`SUPABASE_KEY`** = the **PROJECT apikey** (anon/publishable) — goes in the `apikey` header.
- **`SUPABASE_TOKEN`** = the **USER access token** (JWT) — goes in `Authorization: Bearer`.
  Only with it does `auth.uid()` resolve, the `owner` gets filled in, and the INSERT passes RLS.

If `SUPABASE_TOKEN` is missing, the Bearer falls back to the apikey itself (good for anon read or
service_role). **Do not** use `service_role` for multi-tenant write: it bypasses RLS and leaves
`owner` null. Never commit a key or token.

## Steps

1. **Create project** — done (the URL above).
2. **Run the schema** — Dashboard → **SQL Editor → New query** → paste
   the schema (generate it with **`lifeline schema`**, or see [`lifeline/schema.sql`](../lifeline/schema.sql))
   → **Run** (or run it via Supabase MCP). It creates:
   - `lifeline_entries` — the ledger, with indexes/dedup/`seq` and **append-only RLS** (only
     SELECT/INSERT of the user's own; UPDATE/DELETE denied by the absence of a policy);
   - `lifeline_proposals` — the **HITL queue** (mutable: SELECT/INSERT/UPDATE by the owner; no
     DELETE → preserves the curation history).
3. **Auth** — enable a provider in Authentication (e-mail/OAuth); obtain the user's access token
   (see the decision above).
4. **Wire the runtime:**
   ```bash
   export SUPABASE_URL=https://rzphncyjrilhwpuemrcl.supabase.co
   export SUPABASE_KEY=<project apikey: anon/publishable>   # don't commit — use .env
   export SUPABASE_TOKEN=<user access token (JWT)>          # required for WRITES under RLS
   ```
   Via the CLI (same seam, remote store):
   ```bash
   lifeline --store supabase verify      # check the chain's integrity in the cloud
   lifeline --store supabase context     # assemble the context from Postgres
   lifeline --store supabase log --kind note --summary "..." --body "..."
   # HITL in the cloud (the AI proposes, the human curates):
   lifeline --store supabase propose --kind decision --summary "..." --body "..."
   lifeline --store supabase review
   lifeline --store supabase approve <pid|all>
   ```
   (In supabase mode, `log/context/verify/rebuild/migrate` work **as does HITL**
   `propose/review/approve/reject`; only `push/pull/clone/lines` stay on the local store.)

   Via code:
   ```python
   from lifeline.cloud import SupabaseEventStore
   store = SupabaseEventStore(line="ledger")   # same EventStore port → state/context/recall identical
   ```
5. **Validate the contract (the session with the MCP/creds runs it):**
   ```bash
   SUPABASE_URL=... SUPABASE_KEY=... SUPABASE_TOKEN=... python -m pytest tests/test_supabase.py -v
   ```
   The 3 `TestSupabaseLive` tests come out of `skip` and prove: a real ledger round-trip, that
   **RLS is append-only** (UPDATE/DELETE denied), and the **HITL round-trip** (propose→pending→
   status). They use the line `lifeline_selftest` (they do not pollute `ledger`).
6. **Web chats (later):** serve the remote MCP (SSE) + REST (PostgREST already exists) with OAuth.
   That is what plugs into claude.ai / ChatGPT / Gemini. Next step of Tier 1 (#0049).

## Why this fits without rewriting

The `EventStore` is a **port**. The `SupabaseEventStore` is just another adapter — `state`, `context`,
`recall`, and the CLI work the same, swapping the local SQLite for Postgres. `httpx` is a dep of the
core (it already came via `mcp`); there's the `lifeline-context[cloud]` extra as an explicit alias.

## State and what's missing

- ✅ Ledger in the cloud (`SupabaseEventStore`) + append-only RLS — validated live (#0042).
- ✅ HITL in the cloud (`SupabaseStagingStore`, table `lifeline_proposals`) — propose/review/
  approve/reject in `--store supabase` mode; mocked wire + skip-gated live round-trip.
- ⏳ Ergonomic CLI auth (user login → cached JWT); today it's via env.
- ⏳ Remote MCP server (SSE) + deploy → web chats surface (claude.ai/ChatGPT/Gemini).
