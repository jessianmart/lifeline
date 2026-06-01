# Remote MCP (HTTP/SSE) — the cloud surface

The **same** MCP surface as local mode, served over HTTP — so an AI can connect from outside
(not just via stdio). Identical resources/tools, write **stays HITL**:

- **Read:** resource `lifeline://project/context` + tool `lifeline_recall`.
- **Propose (HITL):** tools `lifeline_append` / `lifeline_recontextualize` → enter as
  PENDING; a human approves (`lifeline review`/`approve`) before entering the line.

Backend chosen by env (same factory as the CLI): local SQLite **or** Supabase (cloud).

## Run

```bash
# cloud (multi-tenant via RLS) — requires the schema applied (cloud/schema.sql)
export LIFELINE_STORE=supabase
export SUPABASE_URL=https://rzphncyjrilhwpuemrcl.supabase.co
export SUPABASE_KEY=<project apikey>      # don't commit — use .env
export SUPABASE_TOKEN=<JWT access token>  # write under RLS
export LIFELINE_MCP_HOST=0.0.0.0 LIFELINE_MCP_PORT=8000
lifeline-mcp-remote
```

- Transport: `LIFELINE_MCP_TRANSPORT=sse` (default) → endpoints `GET /sse` + `POST /messages`;
  or `streamable-http` → `/mcp`.
- Local backend (no cloud): omit `LIFELINE_STORE` → SQLite (`LIFELINE_DB`).
- Line: `LIFELINE_LINE=<name>` (default `ledger`).
- Behind a tunnel/proxy/deploy, the public Host is allowed by default; pin it with
  `LIFELINE_MCP_ALLOWED_HOSTS=host1,host2` (#0054).

## Deploy (zero-cost, honest)

It's a **Python** server (FastMCP + uvicorn/starlette). It does **NOT** run on Supabase Edge
Functions (those are Deno/TypeScript). Zero-/low-cost routes:

- **Render / Railway / Fly.io** (free/cheap tier) — a single `lifeline-mcp-remote` process with the
  env vars; Supabase remains the store. Step-by-step in `docs/DEPLOY.md`.
- Your own **container** (`pip install lifeline-context[cloud]` + the env vars; a `Dockerfile` ships).
- Dev/local exposed via tunnel (cloudflared/ngrok) for quick testing.

Supabase stays free as the **store** (Postgres+RLS); the host only runs the MCP process.

## OAuth / multi-tenant (Resource Server) — `LIFELINE_OAUTH=1`

Turn it on with `LIFELINE_OAUTH=1` (+ `LIFELINE_STORE=supabase` + `SUPABASE_URL`/`KEY`). The server
becomes an **OAuth 2.1 Resource Server**:

- Requires `Authorization: Bearer <user JWT>` on every request; validates against Supabase
  (`/auth/v1/user`). Invalid/expired → **401**.
- Scopes the store by **that user's JWT** → real multi-tenant via RLS (`owner=auth.uid()`):
  each user only sees/proposes in their own line. (Without `LIFELINE_OAUTH`, it's single-tenant via
  the environment's `SUPABASE_TOKEN`.)
- Publishes the **discovery** at `GET /.well-known/oauth-protected-resource` (RFC 9728), pointing
  to the Authorization Server (`LIFELINE_OAUTH_ISSUER`, default `…/auth/v1`).

```bash
export LIFELINE_OAUTH=1 LIFELINE_STORE=supabase
export SUPABASE_URL=… SUPABASE_KEY=<apikey>
export LIFELINE_MCP_PUBLIC_URL=https://your-host   # public url (goes into the metadata)
lifeline-mcp-remote
```

**Connect right now via the CLIs (NOT via the web apps):** **Claude Code** and the **Gemini CLI**
accept a token by header — e.g.: `claude mcp add --transport http lifeline https://your-host/mcp --header "Authorization: Bearer <jwt>"`.
⚠️ **claude.ai web and ChatGPT do NOT accept a static Bearer** (`static_bearer` not supported);
on the hosted apps it's **authless** or **OAuth** — see below.

## Connecting on the web apps (claude.ai / ChatGPT) — what the research confirmed (Jun/2026)

- **claude.ai accepts an AUTHLESS connector** (`auth: "none"`) → "connect in one click" with **no
  AS at all** — but **without per-user identity** (good for single-tenant / a shared line, not
  multi-tenant). Great for **validating** the value before investing in the AS.
- **Multi-tenant (each user sees their own) requires an Authorization Server** (authorize+token+PKCE+
  metadata). **BUT DCR is NOT mandatory:** claude.ai accepts **CIMD** or a **pre-registered
  client** (creds via `mcp-review@anthropic.com`); ChatGPT accepts CIMD/predefined clients.
  DCR only removes the manual setup.
- **A static Bearer doesn't work** on the web apps (only on the CLIs). ChatGPT requires **Developer
  Mode** (paid plans; the free tier doesn't have it).
- **Zero-cost AS with DCR (when you build it):** Cloudflare `workers-oauth-provider` (OSS, free
  Workers), Keycloak (OSS, self-host), Stytch (free ~10K MAU). **Integration gotcha:** the AS must
  yield an identity compatible with Supabase's RLS (`auth.uid()`) — the cleanest way is for the AS
  to use Supabase Auth as the login, or to re-plug the RS into the provider's JWKS.

> Summary: the **Resource Server** (validation + metadata + multi-tenant) is ready and tested.
> For the hosted one-click — **authless validates without an AS**; multi-tenant **needs an AS, not
> DCR**. In all routes, **our RS doesn't change** — it already validates the JWT and scopes per user.
> (Research anchored in line #0052; next step for the AS = #0049.)

## Security

Credentials only via the environment (`.env`, gitignored) — never in a commit. Write is always HITL:
the remote AI **proposes**, the human curates. The server does not expose `approve`/`reject` (curation
is local/trusted), nor the git commands (`push/pull/clone`).
