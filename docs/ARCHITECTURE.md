# Arquitetura do Lifeline

Documento técnico. Para o *porquê* de cada decisão, a fonte é a `LIFELINE.md` (as entradas
`decision` citadas entre colchetes, ex.: `#0002`).

## Visão de 10 mil pés

O Lifeline é um **ledger de raciocínio event-sourced**. Tudo é uma `Entry` imutável,
content-addressed, encadeada num DAG. A "verdade atual" e o contexto que uma IA lê são
**projeções derivadas** desse ledger — nunca a fonte. Três camadas de memória, todas
ancoradas no mesmo ledger:

```
                      Camada 3 · Recall (semântico)
                      embeddings ancorados → "o relevante à tarefa"
                                  ▲
   Entry (append) ──▶ Camada 1 · Ledger ──reduce──▶ Camada 2 · Estado ──assemble──▶ payload
                      (DAG hasheado,                  (verdade atual,                 (markdown,
                       fonte de verdade)               via reducers)                   por budget)
                                  │
                                  └── projection ──▶ LIFELINE.md (view diffável)
```

Mapa de módulos (`lifeline/`):

| Módulo | Camada / papel |
|---|---|
| `entry.py` | a `Entry` content-addressed (identidade) |
| `store.py` | `EventStore` (port) + `SQLiteEventStore` (Camada 1) |
| `state.py` | `StateEngine` + reducers (Camada 2) |
| `recall.py` | `Embedder` + `LexicalEmbedder` + `SemanticRecall` (Camada 3) |
| `context.py` | `ContextAssembler` — monta o payload |
| `projection.py` | store → markdown (a view gerada) |
| `ingest.py` | markdown → store (migração) |
| `cli.py` / `__main__.py` | a CLI `lifeline` |
| `mcp_server.py` | o servidor MCP (`lifeline-mcp`) |

## 1. O modelo de evento — content-addressing determinístico  [#0002, #0003]

```
id = sha256( kind \n author \n agent \n provider \n model \n summary \n body.strip()
             \n "|".join(sorted(parents)) )
```

- `ts` (timestamp) e `dedup_key` ficam **fora** do hash. Consequência: o mesmo conteúdo +
  os mesmos pais geram o **mesmo `id` em qualquer máquina, em qualquer momento**. É o que
  torna dedup e merge entre nós/usuários possíveis (somos *mais* content-puros que o git,
  cujo commit-sha inclui timestamp).
- `parents` é **ordenado** no hash → a identidade é invariante à ordem em que os pais foram
  listados (um merge de A+B = de B+A).
- `pydantic strict=True`. O `id` é selado num `model_validator`; `verify()` recomputa e
  compara (tamper-evidence por entrada).

## 2. Camada 1 — o Ledger (`SQLiteEventStore`)

Append-only. Tabela `entries` (id único, payload JSON, kind, ts, dedup_key, parents) +
tabela `edges` (DAG) + índice único em `dedup_key`. WAL ligado. `append()` é **idempotente**:
viola PK (`id`) ou `dedup_key` → ignora silenciosamente (resolve o problema de "split-brain"
de forma trivial). `stream()` devolve em ordem causal de inserção (single-writer). É a
**fonte de verdade de runtime**.

`EventStore` é uma **port abstrata** — o `SQLiteEventStore` é o adapter local; um
`SupabaseEventStore` (M3) implementa a mesma interface sem tocar no core. É a costura da nuvem.

## 3. Camada 2 — o Estado (`StateEngine` + reducers)

Dobra o stream em "verdade atual" via reducers puros `(estado, entry) -> estado`. O reducer
padrão `ledger_projection` produz: identidade (`project`), `decisions` em vigor, `open_items`,
`latest`, `contributors` (autoria agregada por provider/modelo), `kinds`, e `superseded`.

**Status é projeção, não FSM** [#0002]: nada de máquina de estados de execução; o "estado" é
o que os reducers calculam. Reducers customizados podem ser registrados.

**Supersessão** [#0018]: ao encontrar uma `correction`, seus `parents` entram no conjunto
`superseded`; decisões e threads abertas com esse id saem da verdade atual. Append-only:
fechar/reverter é uma entrada *nova*, nunca edição.

## 4. Camada 3 — Recall (`SemanticRecall` + `Embedder`)

`Embedder` é plugável [#0015]: um modelo por índice. Default `LexicalEmbedder` —
term-frequency esparso, cosseno **exato**, determinístico, sem dependência. (Tentamos hashing
primeiro; o teste pegou colisão de buckets gerando falsa relevância → TF esparso dá 0 exato
sem token compartilhado.) `SemanticRecall.search(query, k)` devolve top-k **ancorado** ao
evento (Lei #1) — o vetor é só índice; errar o match não vira alucinação. Um embedder
semântico denso (sentence-transformers/API) pluga atrás da mesma interface (`#0029`, aberto).

## 5. Montagem (`ContextAssembler`)

Renderiza **markdown** [#0010] (mais token-eficiente que JSON/YAML para LLMs) dentro de um
budget. **Prioridade de orçamento:** header + "Relevante" (se houver `query`) + "Em aberto" +
"Recente" são sempre incluídos; as decisões preenchem o resto, mantendo as **mais recentes** e
omitindo as antigas com **marcador explícito** (Lei #6 — truncamento nunca silencioso). Itens
superseded aparecem marcados `[fechado/revertido]` na "Recente".

## 6. Projeção e o cutover store-é-fonte  [#0014, #0020, #0022]

`render_ledger_markdown(store)` gera a `LIFELINE.md` a partir do ledger. `ingest_markdown`
faz o caminho inverso. Os dois formam um **ponto fixo** (provado): store → markdown → store
reproduz os mesmos `id`s, e o 2º render é byte-idêntico.

Isso unificou os dois esquemas de hash que coexistiam (cadeia markdown vs id do Entry) no
`id` content-addressed. **Decisão de artefato git** [#0022]: o que se commita é o **texto**
(`LIFELINE.md`, diffável/mergeável em PR); o `.lifeline/*.db` é **cache local** (gitignored),
reconstruível com `lifeline migrate`. Como texto↔store são losslessly interconversíveis, a
fonte de verdade é *o conjunto de entradas content-addressed*, materializado como ambos.

## 7. Superfície MCP (`mcp_server.py`)  [Lei #7]

Fecha o loop sem humano. **Resource** `lifeline://project/context` (leitura) + **tools**
`lifeline_append`, `lifeline_recontextualize`, `lifeline_recall` (escrita/recall). DB via env
`LIFELINE_DB` (default `.lifeline/ledger.db`, relativo ao cwd → cada projeto sua própria line).

## Invariantes (resumo)

1. Nenhuma memória sem âncora imutável.  2. Append-only.  3. Content-addressing determinístico.
4. Storage agnóstico de provider; entrega por provider.  5. Porquê > quê.  6. Budget
first-class (truncamento explícito).  7. MCP-native.
