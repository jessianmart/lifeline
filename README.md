# Lifeline

> **A context runtime for AI-assisted development.** The project stores *why* it is what it
> is — and any AI connects and **already knows**, with no human re-explaining.

🌐 **English** · [Português](README.pt-BR.md)

![status](https://img.shields.io/badge/status-alpha-orange) ![python](https://img.shields.io/badge/python-3.10%2B-blue) ![tests](https://img.shields.io/badge/tests-75%20passing-brightgreen) ![license](https://img.shields.io/badge/license-MIT-green)

In one line, it's **"git for reasoning"**: just as git versions *what* changed in the code,
Lifeline versions *why* — decisions, reversals, incidents, the current state — in an
append-only, content-addressed ledger that lives inside the project. Any model (Claude, GPT,
Gemini), in any session, reconstructs the context the moment it connects via MCP.

---

## The problem

AI assistants are **stateless across sessions**. With every new session, agent, or provider,
the human becomes the memory bus — re-explaining decisions that already existed. The naive
fix (a living markdown log) works until it blows past the context window. "Memory" tools
store text/vectors with no provenance → hallucinated recall.

## The idea

The **north star** is a single metric — **Time-to-Context (TTC) → 0** — operationalized by an
acceptance test:

> A fresh AI connects, **with no human in the loop**, and correctly answers:
> **what / why / what's decided / what's next?**

Lifeline keeps the project's "lifeline" (the `LIFELINE.md`) and makes it **queryable,
compressible, and anchored** — so it never overflows the window and never hallucinates.

---

## Install

```bash
pip install lifeline-context        # once published to PyPI
pip install -e .                    # or, from the repo root (dev) → installs lifeline, lifeline-mcp, lifeline-mcp-remote
pip install -e ".[cloud]"           # optional: cloud mode (Supabase) — pulls httpx explicitly
```

Dependencies: `pydantic`, `aiosqlite`, `mcp`, `httpx`. Python ≥ 3.10.

## Quickstart (CLI)

```bash
# In ANY of your projects — each gets its own .lifeline/ledger.db:
lifeline log --kind bootstrap --summary "Bootstrap project X" --body "Multi-tenant billing API."
lifeline log --kind decision  --summary "DB: PostgreSQL"      --body "ACID required by audit."

lifeline context                       # prints the assembled current truth (what an AI reads)
lifeline context --query "database"    # prioritizes what's relevant to the task (Layer 3)
lifeline verify                        # checks the chain's integrity
```

`LIFELINE.md` regenerates on every `log` — **don't hand-edit it**. On a fresh clone without
`.lifeline/`, rebuild the cache with `lifeline migrate --from LIFELINE.md`.

## Connect it to your AI (zero config in Claude Code)

Lifeline ships a local **MCP server** (`lifeline-mcp`, stdio). On connect, the AI gets the
`lifeline://project/context` resource + tools (`lifeline_recall`, and write tools that are
**HITL** — they *propose*; the human approves). Server config is in [`.mcp.json`](.mcp.json):

```json
{ "mcpServers": { "lifeline": {
    "command": "lifeline-mcp", "args": [],
    "env": { "LIFELINE_DB": ".lifeline/ledger.db" } } } }
```

- **Claude Code** reads `.mcp.json` **automatically**.
- **Cursor / Claude Desktop / Gemini CLI:** copy-paste snippets in [`docs/INTEGRATION.md`](docs/INTEGRATION.md).
- **Web chat apps** (claude.ai, ChatGPT) need a remote server + OAuth — see [`docs/MCP_REMOTE.md`](docs/MCP_REMOTE.md).

## Quickstart (Python SDK)

```python
import asyncio
from lifeline import Entry, SQLiteEventStore, StateEngine, ContextAssembler, SemanticRecall

async def main():
    store = SQLiteEventStore(".lifeline/ledger.db")
    await store.initialize()
    await store.append(Entry(kind="decision", author="me",
                             summary="DB: PostgreSQL", body="ACID for audit."))
    ctx = await ContextAssembler(StateEngine(store)).assemble()   # ready to inject into a prompt
    print(ctx)
    hits = await SemanticRecall(store).search("which database", k=3)  # anchored relevance

asyncio.run(main())
```

---

## The loop (do both sides)

- **On connect:** load the context (`lifeline context` or the MCP resource) before acting.
- **While working:** on each decision/feature/fix/incident, **append** (`lifeline log` or
  `lifeline_append`). Reversed something? `lifeline_recontextualize` (supersede by id).

```
   CONNECT (read)                                                      WRITE (append)
   lifeline context        ┌─────────────┐  reduce  ┌──────────┐  rank+  lifeline log
   MCP resource ──────────▶│  Layer 1    │─────────▶│ Layer 2  │ budget  lifeline_append
   lifeline://…/context    │  Ledger     │          │ State    │────────▶ (HITL: propose)
   Layer 3 (recall) ──────▶│  (immutable │          │ (current │
   anchored relevance      │   DAG)      │          │  truth)  │
                           └──────┬──────┘          └────┬─────┘
                                  │ projection (store → markdown) ▼
                                  └──────────────▶ LIFELINE.md (generated view, git-diffable)
```

## Core concepts

- **Entry** — the atomic unit. Content-addressed: `id = sha256(kind, author, agent, provider,
  model, summary, body, sorted-parents)`. `ts` and `dedup_key` are **outside** the hash → the
  same content yields the same `id` on any machine (the basis for dedup and sync).
- **3 memory layers** (all anchored to the immutable ledger): **Ledger** (hashed append-only
  DAG, source of truth) · **State** (current truth reduced via reducers; status is a
  projection, not a state machine) · **Recall** (relevance search; every hit anchored to its
  source event).
- **Supersession** — a `correction` referencing another entry's `id` removes it from the
  current truth (reverted decision, closed thread). Append-only: the past is never edited.
- **Anti-hallucination anchor** — every item the AI reads carries its source event's hash.
  No anchor, no entry.

Full detail in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## CLI reference

| Command | What it does |
|---|---|
| `lifeline log --kind … --summary … [--body … --parents id,…]` | **human:** append directly to the line (you're the approver) + regenerate the view |
| `lifeline propose --kind … --summary … --body …` | propose an entry (**HITL**) — stays pending, not in the line |
| `lifeline review` · `approve <pid\|all>` · `reject <pid\|all>` | HITL curation: list / seal / discard |
| `lifeline context [--query "…"] [--budget N]` | print the assembled current truth (relevance if `--query`) |
| `lifeline verify` | check that every `id` matches its content |
| `lifeline rebuild` · `migrate --from LIFELINE.md` | regenerate the view / rebuild the `.db` from markdown |
| `lifeline lines` | list the project's lines (`.lifeline/*.db`) |
| `lifeline push` · `pull` · `clone <url> <dir>` | **git sync** (Tier 0, zero cost): the text view syncs; the `.db` rebuilds |

**Write tiering (like approving a shell command):** the human's `log` commits directly (they're
the approver); the **AI via MCP `propose`** enters as a **pending** proposal (HITL), and a human
**approves** before it becomes truth. Write-time anti-junk requires the *why*; junk never enters.

Globals: `--db` (default `.lifeline/ledger.db`) · **`--line <name>`** maps a named *line* —
ledger **and** view together (`.lifeline/<name>.db` + `LIFELINE.<name>.md`), no collisions.
A **line** = one reasoning ledger (code *or* conversation); a project has 1 by default, supports N.

## Local → cloud (graduation)

Everything is content-addressed → **pushing a local line to the cloud is lossless and
idempotent**: same ids, re-seed dedupes itself.

```bash
lifeline --store supabase migrate --from LIFELINE.md   # seed (repeatable — no dupes)
lifeline --store supabase context                       # now operate against the cloud
```

Just share the *text* (no cloud)? `lifeline push` (Tier 0 — git). Cloud setup + auth:
[`docs/M3_TIER1_SUPABASE.md`](docs/M3_TIER1_SUPABASE.md) · `.env.example`.

## The 7 laws (the constitution)

1. **No memory without an immutable anchor** (anti-hallucination). 2. **Append-only** (corrections
are new entries). 3. **Deterministic content-addressing.** 4. **Provider-agnostic storage; deliver
in the provider's format.** 5. **The *why* outweighs the *what*.** 6. **Budget is first-class**
(truncation always explicit). 7. **MCP-native.**

**Non-goals:** Lifeline is NOT a cognitive OS, MMU, agent orchestrator/sandbox, workflow engine,
a git replacement, an executor/curator (self-healing), or a trainer (fine-tuning). **It records
reasoning, not execution.**

## Status & roadmap

**Alpha.** Solid, proven **local single-user** core — correctness locked by tests (determinism,
anti-tamper, supersession, round-trip fixed-point). **Cloud (M3) functional and live-validated.**
75 tests green; CI on GitHub Actions.

| Milestone | State |
|---|---|
| **M1 / M1.5** — the loop (ledger→state→assembly→MCP), authorship, recall, CLI, store-is-source | ✅ done |
| **M3 Tier 0** — git sync | ✅ done |
| **M3 Tier 1** — Supabase store + append-only RLS + cloud HITL | ✅ live-validated |
| **M3** — remote MCP (HTTP/SSE) + OAuth **Resource Server** (multi-tenant) | ✅ done |
| **M2** — dense semantic embedder (default is lexical) | open (#0029) |
| **OAuth Authorization Server** (DCR/auth-code for hosted connectors) | open (#0049) |
| **M4** — multi-user (concurrent DAG merge) / hub | planned |

**Honest limits today:** recall is lexical (keywords, not meaning — #0029); a hosted **paid**
cloud needs the AS + billing (#0049) — today it's **local OSS + bring-your-own-Supabase**; no
retry/backoff in the cloud adapter yet (log+raise only).

## Built by dogfooding

Lifeline was rebuilt **using itself from entry #0001**: every decision became an anchored entry
in `LIFELINE.md`. The process surfaced **real bugs in actual use** that unit tests missed
(taxonomy, encoding, false relevance) — all recorded. The proof it works is that the repo needs
no one to explain it.

## Contributing & license

The rule is the constitution: **if you touched it, append to the line.** See
[`CONTRIBUTING.md`](CONTRIBUTING.md) · [`AGENTS.md`](AGENTS.md) · [`llms.txt`](llms.txt).
Licensed [MIT](LICENSE) — open-source core; cloud mode is open-core.
