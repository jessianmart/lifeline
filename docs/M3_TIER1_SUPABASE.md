# M3 Tier 1 — Supabase

Pluga o Lifeline na nuvem para o sync entre dispositivos/usuários e (depois) os chats web.
**Sem Redis** (decisão #0038): Postgres = store, Auth = OAuth, RLS = tenant, Realtime = push.

> Status: **adapter promovido ao pacote (`lifeline/cloud.py`) e coberto por testes de
> transporte mockados** (`tests/test_supabase.py`). O **contrato real** (schema/RLS/PostgREST)
> é provado pelo **teste live skip-gated** — que roda quando `SUPABASE_URL`/`KEY` estão no
> ambiente. Até esse teste passar contra um projeto, trate como *"wired, não validado ao vivo"*.

Projeto: `https://rzphncyjrilhwpuemrcl.supabase.co` (ref `rzphncyjrilhwpuemrcl`).

## Segurança (leia primeiro)

- **Nunca** cole a `service_role` key nem a senha do banco em chat ou em commit.
- O passo do schema (abaixo) roda **no seu Dashboard** — não exige compartilhar key nenhuma.
- O runtime lê do **ambiente** (`SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_TOKEN`); use um
  `.env` (já no `.gitignore`).

## Auth — decisão (importante)

O gateway do Supabase exige **DOIS valores distintos** (validado ao vivo, #0042 — usar o JWT
como `apikey` dá `401 Invalid API key`):

- **`SUPABASE_KEY`** = a **apikey do PROJETO** (anon/publishable) — vai no header `apikey`.
- **`SUPABASE_TOKEN`** = o **access token do USUÁRIO** (JWT) — vai no `Authorization: Bearer`.
  Só com ele `auth.uid()` resolve, o `owner` é preenchido e o INSERT passa na RLS.

Se `SUPABASE_TOKEN` faltar, o Bearer cai na própria apikey (serve p/ leitura anon ou
service_role). **Não** use `service_role` para escrita multi-tenant: bypassa a RLS e deixa
`owner` nulo. Nunca comite key nem token.

## Passos

1. **Criar projeto** — feito (a URL acima).
2. **Rodar o schema** — Dashboard → **SQL Editor → New query** → cole
   [`cloud/schema.sql`](../cloud/schema.sql) → **Run** (ou rode via Supabase MCP). Cria
   `lifeline_entries` com índices, dedup, `seq` e **RLS append-only** (só SELECT/INSERT do
   próprio usuário; UPDATE/DELETE negados pela ausência de policy).
3. **Auth** — habilite um provider em Authentication (e-mail/OAuth); obtenha o access token
   do usuário (ver decisão acima).
4. **Wire do runtime:**
   ```bash
   export SUPABASE_URL=https://rzphncyjrilhwpuemrcl.supabase.co
   export SUPABASE_KEY=<apikey do projeto: anon/publishable>   # NÃO comite — use .env
   export SUPABASE_TOKEN=<access token de usuário (JWT)>       # necessário p/ ESCRITA sob RLS
   ```
   Via CLI (mesmo seam, store remoto):
   ```bash
   lifeline --store supabase verify      # checa integridade da cadeia na nuvem
   lifeline --store supabase context     # monta o contexto a partir do Postgres
   lifeline --store supabase log --kind note --summary "..." --body "..."
   ```
   (`push/pull/clone/lines` e o HITL são do store local; no modo supabase use
   `log/context/verify/rebuild/migrate`.)

   Via código:
   ```python
   from lifeline.cloud import SupabaseEventStore
   store = SupabaseEventStore(line="ledger")   # mesmo port EventStore → state/context/recall iguais
   ```
5. **Validar o contrato (a sessão com o MCP/creds roda):**
   ```bash
   SUPABASE_URL=... SUPABASE_KEY=... SUPABASE_TOKEN=... python -m pytest tests/test_supabase.py -v
   ```
   Os 2 testes `TestSupabaseLive` saem do `skip` e provam: round-trip real e que a **RLS é
   append-only** (UPDATE/DELETE negados). Usam a line `lifeline_selftest` (não poluem `ledger`).
6. **Chats web (depois):** servir o MCP remoto (SSE) + REST (PostgREST já existe) com OAuth.
   É o que pluga em claude.ai / ChatGPT / Gemini. Próximo passo do Tier 1.

## Por que isso encaixa sem reescrever

O `EventStore` é um **port**. O `SupabaseEventStore` é só outro adapter — `state`, `context`,
`recall` e a CLI funcionam igual, trocando o local SQLite pelo Postgres. `httpx` é dep do
core (já vinha via `mcp`); há o extra `lifeline-context[cloud]` como alias explícito.

## O que ainda falta (depois do contrato validado)

- Auth do CLI ergonômica (login do usuário → JWT em cache), hoje é via env.
- HITL (`propose`/`approve`) escrevendo na nuvem (hoje a staging é local SQLite).
- Servidor MCP remoto (SSE) + deploy → superfície dos chats web.
