# MCP remoto (HTTP/SSE) — a superfície da nuvem

A **mesma** superfície MCP do modo local, servida por HTTP — pra uma IA conectar de fora
(não só via stdio). Recursos/tools idênticos, escrita **continua HITL**:

- **Ler:** resource `lifeline://project/context` + tool `lifeline_recall`.
- **Propor (HITL):** tools `lifeline_append` / `lifeline_recontextualize` → entram como
  PENDENTES; um humano aprova (`lifeline review`/`approve`) antes de entrar na line.

Backend escolhido por env (mesmo factory da CLI): SQLite local **ou** Supabase (nuvem).

## Rodar

```bash
# nuvem (multi-tenant via RLS) — precisa do schema aplicado (cloud/schema.sql)
export LIFELINE_STORE=supabase
export SUPABASE_URL=https://rzphncyjrilhwpuemrcl.supabase.co
export SUPABASE_KEY=<apikey do projeto>      # NÃO comite — use .env
export SUPABASE_TOKEN=<access token JWT>      # escrita sob RLS
export LIFELINE_MCP_HOST=0.0.0.0 LIFELINE_MCP_PORT=8000
lifeline-mcp-remote
```

- Transporte: `LIFELINE_MCP_TRANSPORT=sse` (default) → endpoints `GET /sse` + `POST /messages`;
  ou `streamable-http` → `/mcp`.
- Backend local (sem nuvem): omita `LIFELINE_STORE` → SQLite (`LIFELINE_DB`).
- Line: `LIFELINE_LINE=<nome>` (default `ledger`).

## Deploy (zero-custo, honesto)

É um servidor **Python** (FastMCP + uvicorn/starlette). **NÃO** roda em Supabase Edge
Functions (essas são Deno/TypeScript). Rotas de custo-zero/baixo:

- **Fly.io / Render / Railway** (free tier) — um processo `lifeline-mcp-remote` com as env
  vars; o Supabase continua sendo o store.
- **Container** próprio (`pip install lifeline-context[cloud]` + as env vars).
- Dev/local exposto por túnel (cloudflared/ngrok) pra testar rápido.

O Supabase segue de graça como **store** (Postgres+RLS); o host só roda o processo MCP.

## Conectar nas IAs de chat — o que falta (sem overclaim)

Os conectores de **claude.ai / ChatGPT / Gemini** exigem **OAuth 2.1** no endpoint MCP
(discovery + autorização). Este servidor **ainda não tem OAuth** — então hoje ele conecta
em clientes MCP que aceitam uma URL crua (clientes próprios, a ponte `mcp-remote`,
`claude mcp add --transport sse <url>`). Wirar o OAuth pros conectores hospedados é o
**próximo incremento**.

Relacionado: hoje o servidor é **single-tenant** (usa UM `SUPABASE_TOKEN` do ambiente).
O multi-tenant de verdade (cada usuário autentica e o servidor usa o JWT dele) vem junto
com o OAuth — a tabela e a RLS já estão prontas pra isso (`owner = auth.uid()`).

## Segurança

Credenciais só via ambiente (`.env`, gitignored) — nunca em commit. Escrita sempre HITL:
a IA remota **propõe**, o humano cura. O servidor não expõe `approve`/`reject` (curadoria
é local/confiável), nem os comandos de git (`push/pull/clone`).
