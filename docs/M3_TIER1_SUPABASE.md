# M3 Tier 1 — Supabase (kit)

Pluga o Lifeline na nuvem para o sync entre dispositivos/usuários e (depois) os chats web.
**Sem Redis** (decisão #0038): Postgres = store, Auth = OAuth, RLS = tenant, Realtime = push.

> Status: **kit de referência, não-testado** até rodar contra um projeto real. O adapter
> (`cloud/supabase_store.py`) fica FORA do core testado (`lifeline/`) e é promovido — com
> testes — quando validado.

Projeto: `https://rzphncyjrilhwpuemrcl.supabase.co` (ref `rzphncyjrilhwpuemrcl`).

## Segurança (leia primeiro)

- **Nunca** cole a `service_role` key nem a senha do banco em chat ou em commit.
- O passo do schema (abaixo) roda **no seu Dashboard** — não exige compartilhar key nenhuma.
- O runtime lê as keys do **ambiente** (`SUPABASE_URL`, `SUPABASE_KEY`); use um `.env`
  (já no `.gitignore`).

## Passos

1. **Criar projeto** — feito (a URL acima).
2. **Rodar o schema** — Dashboard → **SQL Editor → New query** → cole o conteúdo de
   [`cloud/schema.sql`](../cloud/schema.sql) → **Run**. Cria `lifeline_entries` com índices,
   dedup e **RLS append-only** (só SELECT/INSERT do próprio usuário; UPDATE/DELETE negados).
3. **Auth** — habilite um provider em Authentication (e-mail/OAuth). O `owner` de cada
   entrada é o `auth.uid()` do usuário logado; a RLS isola por tenant automaticamente.
4. **Wire do runtime** (quando formos promover):
   ```bash
   export SUPABASE_URL=https://rzphncyjrilhwpuemrcl.supabase.co
   export SUPABASE_KEY=<access token do usuário ou anon key>   # NÃO comite
   ```
   ```python
   from cloud.supabase_store import SupabaseEventStore
   store = SupabaseEventStore(line="ledger")   # mesmo port EventStore → state/context/recall iguais
   ```
5. **Chats web (depois):** servir o MCP remoto (SSE) + REST (PostgREST já existe) com OAuth.
   É o que pluga em claude.ai / ChatGPT / Gemini. Próximo passo do Tier 1.

## Por que isso encaixa sem reescrever

O `EventStore` é um **port**. O `SupabaseEventStore` é só outro adapter — `state`, `context`,
`recall`, `staging` e a CLI funcionam igual, trocando o local SQLite pelo Postgres. O sync
local↔nuvem é o mesmo protocolo content-addressed (delta por id, append-only, idempotente).

## O que falta para promover ao core testado

- Validar `append`/`get`/`stream` contra o projeto real (escrever `tests/test_supabase.py`
  que roda só quando `SUPABASE_URL`/`KEY` estão setadas — senão `skip`).
- Decidir auth do CLI (login do usuário → JWT) e o flag `--store supabase`.
- Servidor MCP remoto (SSE) + deploy.
