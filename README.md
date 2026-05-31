# Lifeline

> **Runtime de contexto para desenvolvimento com IA.** O projeto guarda *por que* ele
> é o que é — e qualquer IA conecta e **já sabe**, sem humano reexplicando.

![status](https://img.shields.io/badge/status-alpha-orange) ![python](https://img.shields.io/badge/python-3.10%2B-blue) ![tests](https://img.shields.io/badge/tests-8%20suites%20passing-brightgreen) ![license](https://img.shields.io/badge/license-MIT-green)

É, em uma frase, **o "git do raciocínio"**: assim como o git versiona *o quê* mudou no
código, o Lifeline versiona *por quê* — decisões, reversões, incidentes, o estado atual —
num ledger append-only, content-addressed, que vive dentro do projeto. Qualquer modelo
(Claude, GPT, Gemini), em qualquer sessão, reconstrói o contexto ao conectar via MCP.

---

## O problema

Assistentes de IA são **stateless entre sessões**. A cada nova sessão, agente ou provider,
o humano vira o barramento de memória — reexplicando decisões que já existiam. A correção
ingênua (um log markdown vivo) funciona até estourar a janela de contexto. Ferramentas de
"memória" guardam texto/vetores sem proveniência → recall alucinado.

## A ideia

O **norte** é uma métrica única — **Tempo-até-Contexto (TTC) → 0** — operacionalizada por um
teste de aceitação:

> Uma IA nova conecta, **sem humano no meio**, e responde corretamente:
> **o quê / por quê / o que está decidido / o que vem a seguir?**

O Lifeline guarda a "linha de vida" do projeto (a `LIFELINE.md`) e a torna
**consultável, comprimível e ancorada**, para nunca estourar a janela e nunca alucinar.

---

## Instalação

```bash
pip install -e .          # a partir de v2/  → instala os comandos `lifeline` e `lifeline-mcp`
# ou, da raiz do repo:    pip install -e v2
```

Dependências: `pydantic`, `aiosqlite`, `mcp`. Python ≥ 3.10.

## Quickstart (CLI)

```bash
# Em QUALQUER projeto seu — cada projeto ganha seu próprio .lifeline/ledger.db:
lifeline log --kind bootstrap --summary "Funda o projeto X" --body "API de cobrança multi-tenant."
lifeline log --kind decision  --summary "Banco: PostgreSQL"  --body "ACID exigido por auditoria."

lifeline context                       # imprime a verdade atual montada (o que uma IA lê)
lifeline context --query "banco"       # prioriza o que é relevante à tarefa (Camada 3)
lifeline verify                        # confere a integridade da cadeia
```

A `LIFELINE.md` se regenera a cada `log` — **não edite à mão**. Num clone novo sem
`.lifeline/`, reconstrua o cache com `lifeline migrate --from LIFELINE.md`.

## Quickstart (SDK Python)

```python
import asyncio
from lifeline import Entry, SQLiteEventStore, StateEngine, ContextAssembler, SemanticRecall

async def main():
    store = SQLiteEventStore(".lifeline/ledger.db")
    await store.initialize()

    await store.append(Entry(kind="decision", author="me",
                             summary="Banco: PostgreSQL", body="ACID por auditoria."))

    # verdade atual montada, pronta pra injetar num prompt:
    ctx = await ContextAssembler(StateEngine(store)).assemble()
    print(ctx)

    # recall por relevância (ancorado ao evento de origem):
    hits = await SemanticRecall(store).search("qual banco de dados", k=3)

asyncio.run(main())
```

---

## O loop (faça os dois lados)

```
            ┌─────────────────────────── a IA dirige os dois lados ──────────────────────────┐
            │                                                                                 │
   CONECTAR ▼ (lê)                                                                ESCREVER ▲ (anexa)
   lifeline context             ┌──────────────┐   reduce   ┌─────────────┐  rank+   │  lifeline log
   resource MCP  ───────────────▶  Camada 1     │──────────▶│  Camada 2   │  budget  │  tool MCP
   lifeline://project/context   │  Ledger (DAG  │           │  Estado     │──────────┤  lifeline_append
                                │  imutável,    │           │  (verdade   │          │  lifeline_recontextualize
        Camada 3 (recall) ──────▶  hasheado)    │           │   atual)    │          │
        relevância ancorada     └──────┬───────┘            └─────┬───────┘          │
                                       │  projection (store → markdown)  ▼            │
                                       └───────────────────▶  LIFELINE.md (view gerada, diffável no git)
```

- **Ao conectar:** carregue o contexto (`lifeline context` ou o resource MCP) antes de agir.
- **Ao trabalhar:** a cada decisão/feature/fix/incidente, **anexe** (`lifeline log` ou
  `lifeline_append`). Reverteu algo? `lifeline_recontextualize` (supersede por id).

---

## Conceitos centrais

- **Entry** — a unidade atômica. Content-addressed: `id = sha256(kind, author, agent,
  provider, model, summary, body, pais-ordenados)`. `ts` e `dedup_key` ficam **fora** do
  hash → o mesmo conteúdo gera o mesmo `id` em qualquer máquina (base do dedup e do sync).
- **As 3 camadas de memória** (todas ancoradas no ledger imutável):
  1. **Ledger (episódico)** — DAG hasheado append-only. A fonte de verdade.
  2. **Estado (operacional)** — a verdade *atual*, reduzida do ledger via reducers. Status é
     projeção, não máquina de estados.
  3. **Recall (semântico)** — busca por relevância; cada resultado ancorado ao evento de origem.
- **Supersessão** — uma `correction` que referencia o `id` de outra entrada a remove da
  verdade atual (decisão revertida, thread fechada). Append-only: o passado nunca é editado.
- **Âncora anti-alucinação** — todo item que a IA lê carrega o hash do evento de origem.
  Sem âncora, não entra.

Detalhe completo em **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**.

---

## Referência — CLI

| Comando | O que faz |
|---|---|
| `lifeline log --kind … --summary … [--body … --parents id,…]` | **humano:** anexa direto na line (você é o aprovador) e regenera a view |
| `lifeline propose --kind … --summary … --body …` | propõe uma entrada (**HITL**) — fica pendente, não entra na line |
| `lifeline review` | lista as propostas pendentes (curadoria) |
| `lifeline approve <pid\|all>` · `lifeline reject <pid\|all>` | HITL: sela na line / descarta |
| `lifeline context [--query "…"] [--budget N]` | imprime a verdade atual montada (com relevância se `--query`) |
| `lifeline verify` | confere que todo `id` bate com seu conteúdo |
| `lifeline rebuild` | regenera a view a partir do store |
| `lifeline migrate --from LIFELINE.md` | reconstrói o `.lifeline/ledger.db` a partir do markdown |
| `lifeline lines` | lista as lines do projeto (`.lifeline/*.db`) |
| `lifeline push` · `lifeline pull` · `lifeline clone <url> <dir>` | **sync via git** (Tier 0, custo zero): a view textual sincroniza; o `.db` se reconstrói |

**Escrita (tiering, como aprovar um comando shell):** o humano no `log` comita direto (é o
aprovador); a **IA via MCP `propose`** — entra como proposta **pendente** (HITL), e um humano
**aprova** (`review`/`approve`) antes de virar verdade. Anti-sujeira no write-time (exige o
*porquê*); junk nunca entra na line.

Globais: `--db` (default `.lifeline/ledger.db`) · **`--line <nome>`** — seleciona uma *line*
nomeada, mapeando ledger **e** view juntos: `.lifeline/<nome>.db` + `LIFELINE.<nome>.md`
(sem colisão entre lines). Sem `--line`, usa a line default. Uma **line** = um ledger de
raciocínio (código *ou* conversa); um projeto tem 1 por default e suporta N.

## Referência — MCP

Servidor: `lifeline-mcp` (stdio). Config em [`.mcp.json`](.mcp.json):

```json
{ "mcpServers": { "lifeline": {
    "command": "lifeline-mcp", "args": [],
    "env": { "LIFELINE_DB": ".lifeline/ledger.db" } } } }
```

- **Resource** `lifeline://project/context` — a linha de vida montada (leia ao conectar).
- **Tools** `lifeline_append`, `lifeline_recontextualize`, `lifeline_recall`.

Integração e hook de auto-connect: **[`docs/INTEGRATION.md`](docs/INTEGRATION.md)**.

## Referência — SDK (principais símbolos)

`Entry` · `SQLiteEventStore` / `EventStore` · `StateEngine` · `ContextAssembler` ·
`SemanticRecall` / `LexicalEmbedder` / `Embedder` · `ingest_markdown` · `render_ledger_markdown`.

---

## Para IAs / AI agents

Esta é a parte que importa: **qualquer IA entende este projeto sem ninguém explicar.**

- **Leia a line:** [`LIFELINE.md`](LIFELINE.md) — comece pela **#0001**. Ou rode
  `lifeline context`. Ou, via MCP, leia o resource `lifeline://project/context`.
- **Obedeça as leis** (abaixo) e **anexe** o que você decidir (`lifeline_append`).
- Onboarding tool-agnóstico em **[`AGENTS.md`](AGENTS.md)** (e [`CLAUDE.md`](CLAUDE.md) para
  Claude Code).

## As 7 leis (a constituição)

1. **Nenhuma memória sem âncora imutável** (anti-alucinação).
2. **Append-only** (correções são entradas novas).
3. **Content-addressing determinístico.**
4. **Storage agnóstico de provider; entrega no formato do provider.**
5. **O *porquê* pesa mais que o *quê*.**
6. **Budget é first-class** (truncamento sempre explícito).
7. **MCP-native.**

## Non-goals (o que o Lifeline **não** é)

NÃO é sistema operacional cognitivo, MMU, orquestrador/sandbox de agentes, workflow
engine, substituto do git, executor/curador (self-healing) nem treinador (fine-tuning).
**Registra raciocínio, não execução.** Ver o *porquê* em `LIFELINE.md` #0002 e #0019.

---

## Status & roadmap

**Alpha — núcleo single-user local funcional e provado.** 8 suítes de teste verdes; teste
de aceitação e prova de fogo adversarial passados; MCP testado ao vivo; pip-installable.

| Fase | Estado |
|---|---|
| **M1** — o laço (ledger → estado → montagem → MCP) | ✅ feito |
| **M1.5** — autoria, threads abertas, relevância (Camada 3), CLI, cutover store-é-fonte | ✅ feito |
| **M2** — embedder semântico denso (o default é lexical) | aberto (`LIFELINE.md` #0029) |
| **M3** — seam de nuvem (Supabase/pgvector/Redis sync) | planejado |
| **M4** — multi-usuário (merge de DAG concorrente) | planejado |

**Limites honestos hoje:** o recall é lexical (casa palavras, não significado); a nuvem
(M3) ainda não existe (só a costura via `EventStore`); docs em PT (EN pendente p/ alcance).

---

## Como foi construído (dogfooding)

O Lifeline foi reconstruído **usando a si mesmo desde a entrada #0001**: cada decisão desta
sessão virou uma entrada ancorada na `LIFELINE.md`. O processo encontrou **bugs reais no
próprio uso** que os testes unitários não pegaram (taxonomia, encoding, falsa relevância) —
todos registrados. A prova de que funciona é o próprio repo não precisar de ninguém para
ser entendido.

## Contribuindo

A regra é a constituição: **se você mexeu, anexe na line.** Ver
**[`CONTRIBUTING.md`](CONTRIBUTING.md)**.

## Licença

[MIT](LICENSE). (Default permissivo para o core open-source; o modo nuvem é open-core.)
