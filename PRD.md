# PRD — Lifeline

> Context runtime for AI-assisted development. The project carries its own
> lifeline of reasoning so that any AI can connect and **already know**.
>
> The living decisions and the *why* behind each one are in [`LIFELINE.md`](LIFELINE.md).
> This PRD is the stable snapshot; the LIFELINE is the append-only truth.

## 1. Problem

AI assistants are stateless between sessions. With each new session/agent/provider,
the human becomes the context bus — re-explaining decisions that already existed. The
naive fix (a living markdown log) works but grows without bound and blows past the
window. "Memory" tools store text/vectors without provenance → hallucinated recall.

## 2. North Star

**Time-to-Context (TTC) → 0.** Acceptance test: *a new AI connects, with no human in the
middle, and correctly answers what / why / what is decided / what comes next.* Today = no.
Done = yes, in seconds.

## 3. Users

v1: solo dev + their AI assistants, local-first. Later: a team with multiple humans + AIs in a
shared context.

## 4. Goals / Non-goals

**Goals:** portable local-first context in the repo; append-only, content-addressed, immutable,
auditable chain; memory anchored to provenance; multi-provider native; MCP-native; scaling
beyond the window (ranking+compression+retrieval); hybrid local OSS + paid cloud.

**Non-goals:** it is NOT an agent orchestrator/sandbox; it is NOT a workflow engine; it does NOT
replace git; v1 is NOT real-time multi-user (the DAG already prepares for it, merge UX comes later).

## 5. Domain model

- **Entry (event):** atomic unit. `id = sha256(content + parents)`, deterministic
  (`ts`/`dedup_key` outside the hash). Fields: id, ts, authorship (human | agent+provider+model),
  kind, summary (the what), body (the why), parents (DAG), hash.
- **Provenance anchor (Invariant #1):** every derivative carries the hash of the origin. No
  anchor → it does not enter.
- **3 memory layers:** (1) episodic ledger — hashed immutable DAG, source of truth; (2)
  operational state — current truth reduced via reducers (status is a projection, not an FSM);
  (3) semantic recall — anchored embeddings.
- **Context assembly:** given a cursor/query, produces a payload that is ranked, compressed, and
  in the provider's format, within a budget.
- **Recontextualization:** first-class human action; corrections are new anchored entries.

## 6. Capabilities

C1 Capture (anchored append) · C2 Integrity (verify chain, drift, dedup) · C3 State reduction
(reducers; status as a projection) · C4 Recall (embed+anchored search) · C5 Assembly
(rank+compress+render per provider) · C6 MCP (context+ledger resources; append/recontextualize
tools) · C7 Projections (timeline, "why", summaries) · C8 Snapshot/sync.

**Functional segmentation (from C5):** fragments tagged by role (procedural / constraint /
objective / grounding / semantic), stored flat and anchored; retrieval picks the dimensions the
*query* needs. A derived layer, never the source. (No write-time "Golden Branch.")

## 7. Laws

See [`CLAUDE.md`](CLAUDE.md) and the protocol in [`LIFELINE.md`](LIFELINE.md). Summary:
immutable anchor · append-only · deterministic content-addressing · provider-agnostic storage /
per-provider delivery · why > what · budget first-class · MCP-native.

## 8. Architecture

Ports & adapters. The core depends only on abstractions (`EventStore`, `StagingStore`, `Embedder`).
Local (OSS): SQLite WAL, in-process cosine vector, markdown projection, MCP stdio. Cloud (paid):
Postgres/Supabase + RLS + Realtime + hosted MCP — **no Redis** (#0038) — swappable without touching
the core.

## 9. Interfaces

- **SDK:** `append()`, `assemble()`, `recall()`, `verify()`.
- **MCP:** resource `lifeline://project/context` (assembled); tools `lifeline_append`,
  `lifeline_recontextualize`, `lifeline_recall`.
- **CLI:** `log`, `context`, `verify`, `rebuild`, `migrate`, `push`/`pull`/`clone`.

## 10. Non-functional

TTC: context assembled in seconds, fixed token budget **independent of the size of the ledger**.
Integrity O(n), tamper-evident. Portable (single file). Privacy in the cloud: tenant isolation
(RLS), opt-in for what leaves the machine. Hashing determinism across machines.

## 11. Hybrid (OSS vs paid)

Local OSS: the entire core (single-user loop, free). Paid (cloud): sync across devices/team,
retrieval at scale, multi-user merge, dashboards. Value = collaboration + scale + zero-ops, not
locking up the core.

## 12. Roadmap

- **M0 Bootstrap (✔):** clean repo, LIFELINE seeded (#0001 + decisions), laws, verifiable hash.
- **M1 The loop (✔):** anchored capture → ledger (deterministic DAG) → state reduction → assembly
  → MCP. Dogfood: ingests its own LIFELINE; the acceptance test runs against the repo itself.
- **M2 Recall + projections:** anchored semantic search (default is lexical; dense embedder #0029,
  open); "why" projection; summaries.
- **M3 Cloud (✔ store/HITL/remote MCP/OAuth RS):** Supabase adapter + RLS + cloud HITL + remote
  MCP (HTTP/SSE) + OAuth Resource Server. Remaining: Authorization Server (#0049).
- **M4 Multi-user:** real DAG merge + recontextualization + conflict / hub.

## 13. Risks

Capture friction (who writes, when — needs low friction without a firehose) · compression fidelity
(don't throw away the why) · determinism vs richness · cloud privacy · the chicken-and-egg of
dogfooding (bridge: markdown now → ingestion in M1).
