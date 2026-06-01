# Lifeline Architecture

Technical document. For *the why* behind each decision, the source is `LIFELINE.md` (the `decision` entries cited in brackets, e.g.: `#0002`).

## 10,000-foot view

Lifeline is an **event-sourced reasoning ledger**. Everything is an immutable, content-addressed `Entry`, chained in a DAG. The "current truth" and the context an AI reads are **derived projections** of that ledger — never the source. Three layers of memory, all anchored in the same ledger:

```
                      Layer 3 · Recall (semantic)
                      anchored embeddings → "what is relevant to the task"
                                  ▲
   Entry (append) ──▶ Layer 1 · Ledger ──reduce──▶ Layer 2 · State ──assemble──▶ payload
                      (hashed DAG,                   (current truth,                (markdown,
                       source of truth)               via reducers)                  by budget)
                                  │
                                  └── projection ──▶ LIFELINE.md (diffable view)
```

Module map (`lifeline/`):

| Module | Layer / role |
|---|---|
| `entry.py` | the content-addressed `Entry` (identity) |
| `store.py` | `EventStore` (port) + `SQLiteEventStore` (Layer 1) |
| `state.py` | `StateEngine` + reducers (Layer 2) |
| `recall.py` | `Embedder` + `LexicalEmbedder` + `SemanticRecall` (Layer 3) |
| `context.py` | `ContextAssembler` — assembles the payload |
| `projection.py` | store → markdown (the generated view) |
| `ingest.py` | markdown → store (migration) |
| `staging.py` | `StagingStore` (port) + `SQLiteStagingStore` — the HITL proposal queue |
| `cli.py` / `__main__.py` | the `lifeline` CLI |
| `mcp_server.py` | the MCP server (`lifeline-mcp` / `lifeline-mcp-remote`) |
| `cloud.py` | Supabase adapters (`SupabaseEventStore`, `SupabaseStagingStore`) — the cloud seam |

## 1. The event model — deterministic content-addressing  [#0002, #0003]

```
id = sha256( kind \n author \n agent \n provider \n model \n summary \n body.strip()
             \n "|".join(sorted(parents)) )
```

- `ts` (timestamp) and `dedup_key` stay **out** of the hash. Consequence: the same content +
  the same parents produce the **same `id` on any machine, at any time**. This is what
  makes dedup and merge across nodes/users possible (we are *more* content-pure than git,
  whose commit-sha includes the timestamp).
- `parents` is **sorted** in the hash → identity is invariant to the order in which the parents
  were listed (a merge of A+B = of B+A).
- `pydantic strict=True`. The `id` is sealed in a `model_validator`; `verify()` recomputes and
  compares (per-entry tamper-evidence).

## 2. Layer 1 — the Ledger (`SQLiteEventStore`)

Append-only. `entries` table (unique id, JSON payload, kind, ts, dedup_key, parents) +
`edges` table (DAG) + unique index on `dedup_key`. WAL on. `append()` is **idempotent**:
violating the PK (`id`) or `dedup_key` → silently ignored (it solves the "split-brain" problem
trivially). `stream()` returns in causal insertion order (single-writer). It is the
**runtime source of truth**.

`EventStore` is an **abstract port** — the `SQLiteEventStore` is the local adapter; the
`SupabaseEventStore` (M3) implements the same interface without touching the core. It is the cloud seam.

## 3. Layer 2 — the State (`StateEngine` + reducers)

Folds the stream into "current truth" via pure reducers `(state, entry) -> state`. The default
reducer `ledger_projection` produces: identity (`project`), `decisions` in effect, `open_items`,
`latest`, `contributors` (authorship aggregated by provider/model), `kinds`, and `superseded`.

**Status is a projection, not an FSM** [#0002]: no execution state machine; the "state" is
what the reducers compute. Custom reducers can be registered.

**Supersession** [#0018]: when a `correction` is encountered, its `parents` enter the `superseded`
set; decisions and open threads with that id leave the current truth. Append-only:
closing/reverting is a *new* entry, never an edit.

## 4. Layer 3 — Recall (`SemanticRecall` + `Embedder`)

`Embedder` is pluggable [#0015]: one model per index. Default `LexicalEmbedder` —
sparse term-frequency, **exact** cosine, deterministic, no dependency. (We tried hashing
first; the test caught a bucket collision producing false relevance → sparse TF gives an exact 0
without a shared token.) `SemanticRecall.search(query, k)` returns top-k **anchored** to the
event (Law #1) — the vector is only an index; getting the match wrong does not turn into a
hallucination. A dense semantic embedder (`SentenceTransformerEmbedder`, #0029) plugs in behind
the same interface — **opt-in** via the `[embeddings]` extra; select it with `LIFELINE_EMBEDDER=dense`
(or `make_embedder(...)`). The default stays lexical (zero-dependency).

## 5. Assembly (`ContextAssembler`)

Renders **markdown** [#0010] (more token-efficient than JSON/YAML for LLMs) within a
budget. **Budget priority:** header + "Relevant" (if there is a `query`) + "Open" +
"Recent" are always included; the decisions fill the rest, keeping the **most recent** ones and
omitting the old ones with an **explicit marker** (Law #6 — truncation is never silent). Superseded
items appear marked `[closed/reverted]` under "Recent".

## 6. Projection and the store-is-source cutover  [#0014, #0020, #0022]

`render_ledger_markdown(store)` generates `LIFELINE.md` from the ledger. `ingest_markdown`
does the reverse path. The two form a **fixed point** (proven): store → markdown → store
reproduces the same `id`s, and the 2nd render is byte-identical.

This unified the two hashing schemes that coexisted (markdown chain vs `Entry` id) into the
content-addressed `id`. **Git artifact decision** [#0022]: what gets committed is the **text**
(`LIFELINE.md`, diffable/mergeable in PRs); the `.lifeline/*.db` is a **local cache** (gitignored),
rebuildable with `lifeline migrate`. Since text↔store are losslessly interconvertible, the
source of truth is *the set of content-addressed entries*, materialized as both.

## 7. MCP surface (`mcp_server.py`)  [Law #7]

Closes the loop without a human. **Resource** `lifeline://project/context` (read) + **tools**
`lifeline_append`, `lifeline_recontextualize`, `lifeline_recall` (write/recall). DB via the env
`LIFELINE_DB` (default `.lifeline/ledger.db`, relative to the cwd → each project its own line).
The same surface runs locally (stdio) and remotely (HTTP/SSE, `lifeline-mcp-remote`, with an
optional OAuth Resource Server) — see `docs/MCP_REMOTE.md`.

## Invariants (summary)

1. No memory without an immutable anchor.  2. Append-only.  3. Deterministic content-addressing.
4. Provider-agnostic storage; per-provider delivery.  5. Why > what.  6. Budget
first-class (explicit truncation).  7. MCP-native.
