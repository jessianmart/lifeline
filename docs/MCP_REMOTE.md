# Remote MCP (HTTP/SSE) — the cloud surface

The **same** MCP surface as local mode, served over HTTP — so an AI can connect from outside
(not just via stdio). Identical resources/tools, write **stays HITL**:

- **Read:** resource `lifeline://project/context` + tool `lifeline_recall`.
- **Propose (HITL):** tools `lifeline_append` / `lifeline_recontextualize` → enter as
  PENDING; a human approves (`lifeline review`/`approve`) before entering the line.

Backend chosen by env (same factory as the CLI): local SQLite **or** Supabase (cloud).

## Run

```bash
# cloud (multi-tenant via RLS) — requires the schema applied (run: lifeline schema)
export LIFELINE_STORE=supabase
export SUPABASE_URL=https://<your-ref>.supabase.co   # your project ref
export SUPABASE_KEY=<project apikey>      # don't commit — use .env
export SUPABASE_TOKEN=<JWT access token>  # write under RLS
export LIFELINE_MCP_HOST=0.0.0.0 LIFELINE_MCP_PORT=8000
lifeline-mcp-remote
```

> **PowerShell:** the `export FOO=bar` blocks below are bash. In PowerShell set each as
> `$env:FOO="bar"` (one per line), then run `lifeline-mcp-remote`.

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

- Requires `Authorization: Bearer <user JWT>` on every request; validates the JWT by **JWKS
  (ES256)** against Supabase's signing keys — offline, no per-request `/auth/v1/user` call
  (#0079). Bad signature / issuer / expiry → **401**.
- Scopes the store by **that user's JWT** → real multi-tenant via RLS (`owner=auth.uid()`):
  each user only sees/proposes in their own line. (Without `LIFELINE_OAUTH`, it's single-tenant via
  the environment's `SUPABASE_TOKEN`.)
- Publishes the **discovery** at `GET /.well-known/oauth-protected-resource` (RFC 9728), pointing
  to the Authorization Server (`LIFELINE_OAUTH_ISSUER`, default `…/auth/v1`). Pointed at Supabase's
  native OAuth Server, this is the **recommended** hosted-connector path (below).

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

## Recommended (hosted connectors): our RS (`LIFELINE_OAUTH=1`) + Supabase's native **OAuth 2.1 Server** as the AS

Supabase shipped a native **OAuth 2.1 Server** (beta) — DCR (RFC 7591) + authorization-code with
**PKCE (S256)** + discovery metadata, MCP-aware. So Supabase **is** the Authorization Server; our
remote MCP stays a thin **Resource Server** (above) and validates the issued JWT by JWKS. This is
the recommended path (#0079): less of our own auth code, and Supabase's hosted login covers social
providers (Google/GitHub).

Setup:

1. **Supabase dashboard → Authentication → OAuth Server:** enable it + **Dynamic Client
   Registration**. Enable Google/GitHub providers if you want social login.
2. **Consent screen (you host it):** Supabase does *not* host the consent/login UI — you build a
   small page (`supabase-js`: `getAuthorizationDetails` → login → `approveAuthorization`) at your
   Site URL + the configured authorization path. A ready page ships in `site/oauth/consent/`.
3. **Run the Resource Server** pointed at Supabase's issuer:

```bash
export LIFELINE_OAUTH=1 LIFELINE_STORE=supabase
export SUPABASE_URL=https://<ref>.supabase.co SUPABASE_KEY=<anon apikey>
# issuer auto-derives to <SUPABASE_URL>/auth/v1; discovery at
#   <SUPABASE_URL>/.well-known/oauth-authorization-server/auth/v1
lifeline-mcp-remote
```

claude.ai then discovers our protected-resource metadata → finds Supabase as the AS → does DCR +
`/authorize` (Supabase hosted login + your consent page) + `/token` directly with Supabase; we
validate the resulting JWT by JWKS. **Beta + multi-party — expect live debugging.**

## Fallback: bundled custom Authorization Server — `LIFELINE_OAUTH_AS=1`

Self-contained AS (no Supabase OAuth Server needed): **complete** DCR (RFC 7591) + authorization-code
with **PKCE (S256)** + discovery metadata (RFC 8414), with login **delegated to Supabase**. Use it
when you can't/don't want to enable Supabase's OAuth Server. It lives in `lifeline/oauth.py`.

```bash
export LIFELINE_OAUTH_AS=1 LIFELINE_STORE=supabase
export SUPABASE_URL=https://<your-ref>.supabase.co SUPABASE_KEY=<anon apikey>
export LIFELINE_MCP_PUBLIC_URL=https://your-host   # we are the issuer → goes into the AS metadata
# --- production hardening (recommended; both on by default when the env is present) ---
export LIFELINE_OAUTH_PROVIDER=github              # hosted social login (no password through us)
export SUPABASE_SERVICE_ROLE=<service_role key>    # persist DCR clients (survives restart/replicas)
pip install 'lifeline-context[cloud,remote]'        # remote = python-multipart (form parsing)
lifeline-mcp-remote
```

Flow (each step is one browser round-trip):

1. `POST /register` — the connector registers itself (DCR). *(SDK route)*
2. `GET /authorize` — we stash the params (PKCE challenge, redirect, state, scopes) under an opaque
   `ticket` and send the browser to **our** `/oauth/login`. *(SDK route)*
3. `GET /oauth/login` — authenticates the user, delegated to Supabase, in one of two modes:
   - **Hosted (production, `LIFELINE_OAUTH_PROVIDER` set):** we redirect the browser to Supabase's
     hosted social login (`/auth/v1/authorize?provider=…`) with **our own** server-side PKCE. **The
     password never touches our server.** GoTrue returns to `/oauth/callback?code=…`. *(our routes)*
   - **Form (dev/CLI, no provider):** a minimal form whose POST relays email+password to Supabase
     (`grant_type=password`). We never store/validate it — Supabase does. *(our route)*
   Either way, success → we mint **our** authorization code (bound to the Supabase session) and
   redirect to the connector's `redirect_uri` with `code`+`state`.
4. `POST /token` — the SDK verifies the **PKCE verifier (S256)** and the redirect; we swap the code
   for `access_token = the Supabase JWT`, which the Resource Server already validates per request
   (scoping the RLS by user). Refresh and revoke also hit Supabase. *(SDK route)*

Discovery: `GET /.well-known/oauth-authorization-server` advertises our `/authorize`, `/token`,
`/register`. `LIFELINE_OAUTH_AS` implies the Resource Server (token introspection via the provider).

**Production hardening (implemented):**
- **Hosted login replaces ROPC.** Set `LIFELINE_OAUTH_PROVIDER` (e.g. `github`, `google`) and step 3
  redirects to Supabase's hosted login — the password never transits our server. The form (ROPC) is
  the **dev/CLI fallback** only, when no provider is configured. **Supabase config:** add
  `https://your-host/oauth/callback` to **Authentication → URL Configuration → Redirect URLs** (use a
  trailing `**` wildcard so the appended `?ticket=…&code=…` query matches), and enable the chosen
  social provider.
- **DCR clients persist.** With `SUPABASE_SERVICE_ROLE` set, registered clients are stored in
  `lifeline_oauth_clients` (service key — registration is pre-login infra, not tenant data) and
  survive restarts/sleep and multiple replicas. Without it, the store is in-memory (fine for a single
  always-on instance). Auth **codes** stay one-time/in-memory (~300s TTL) by design.

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
