# Deploy — AUTHLESS connector for claude.ai (validation)

Goal: prove the **one-click** ("I connect and claude.ai already knows the project context") **without
building an AS** — using the authless mode that claude.ai accepts. It's the **validation** step;
paid multi-tenant comes later with the AS (#0049). Research that backs this: line #0052.

> ⚠️ Reality check (#0057): the **claude.ai WEB connector currently attempts OAuth** and may reject a
> pure-authless server with *"Couldn't register with the sign-in service"*. The authless path works
> reliably from the **CLIs** (Claude Code: `claude mcp add --transport http lifeline <url>/mcp`).
> For the web app you likely need the AS (#0049). This deploy still gives you a real public endpoint
> to validate from the CLIs and to build the AS on top of.

## ⚠️ Security (read first)
Authless + public endpoint = **anyone with the URL reads the context** and can **enqueue
proposals**. Real mitigations:
- The write is **HITL**: the AI only **proposes** (pending); nothing enters the line without your
  approval. The worst an intruder does is **dirty the proposal queue** (you reject it) — it doesn't
  corrupt the line.
- Use a **non-sensitive line** (this demo exposes the project's own LIFELINE.md — public on GitHub
  anyway) and a hard-to-guess URL.
- **Do NOT use authless with private/real data.** For that it's multi-tenant + AS (#0049).

## Deploy on Render (recommended — $0, uses the `Dockerfile`)
The image rebuilds the `.db` from `LIFELINE.md` on boot and serves authless. Two ways:

**A) Blueprint (reads `render.yaml`, fewer clicks):**
1. [render.com](https://render.com) → sign up (GitHub login).
2. **New → Blueprint** → connect the `jessianmart/lifeline` repo → it reads `render.yaml` → **Apply**.

**B) Manual:**
1. **New → Web Service** → connect the repo → **Runtime: Docker** → **Instance Type: Free** → **Create**.

In both cases, wait for the build to finish. The URL is `https://<your-service>.onrender.com`.

**Confirm it came up:** open `https://<your-service>.onrender.com/healthz` in the browser → it should show **`ok`**.

⚠️ **Free tier sleeps after 15 min idle.** The first access wakes the service (~1 min) — if the first
attempt times out, try again. For always-on (no cold start): switch to **Starter ($7/month)** in
`render.yaml` (`plan: starter`) or in the dashboard. (Railway $5/month is the alternative once we
approve its viability.)

> Test locally first (optional, if your network allows it): `lifeline-mcp-remote` + a tunnel
> (`npx cloudflared tunnel --url http://127.0.0.1:8000`). ⚠️ Careful: many networks **block
> cloudflared's port 7844** (ours did) — if the tunnel drops, it's the network; Render solves it.

## Connect a client to the deployed URL
- **Claude Code (works now, authless):** `claude mcp add --transport http lifeline https://<your-service>.onrender.com/mcp`
- **claude.ai web:** Settings → Connectors → Add custom connector → `https://<your-service>.onrender.com/mcp`
  · Authentication: None. (May require the AS — see the reality check above.)

Then, in a conversation, enable the connector and ask something about the project — it answers from
the line context. **That's the test.**

## When you go beyond validation
Multi-tenant (each user their own line) → turn on `LIFELINE_OAUTH=1` + an AS (managed provider with
DCR, or a shim). The **Resource Server is already ready** (`docs/MCP_REMOTE.md`); only the AS (#0049)
is missing.
