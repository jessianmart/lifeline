# Contributing to Lifeline

The rule is the project's constitution: **if you made a significant change, append it to the line.**
Humans and agents obey alike.

## The flow

1. **Connect:** `lifeline context` (or read `LIFELINE.md`, starting from #0001).
2. **Do the work** — one coherent unit at a time.
3. **Append the *why*:**
   ```bash
   lifeline log --kind decision --summary "≤200 chars: the what" --body "the WHY (weighs more)"
   ```
   `kind ∈ {bootstrap, decision, feature, fix, incident, milestone, release, note, open, correction}`.
   - Revert/close something: `lifeline log --kind correction --parents <id> --summary "…"`.
4. **Verify:** `lifeline verify` must return `OK`.

> The store (`.lifeline/ledger.db`) is the source of truth; `LIFELINE.md` is **generated** and
> **must not be edited by hand** — it regenerates on every `log`.

## The rules of a good entry

- **One entry per meaningful unit of work** — not per file, not per tool call.
- **The *why* > the *what*** (Law #5). The `summary` says the what; the `body` says the why, and that
  is what has value for the next AI.
- **Append-only** (Law #2): never edit the past; correct it with a new entry.

## Quality gate

Before declaring any work done:

```bash
python -m pytest        # the suite (live tests skip without SUPABASE_* env)
lifeline verify         # the chain must be intact (OK)
```

- New code only lands **with a test that proves the behavior** (TDD-friendly; the tests are
  dependency-free, `unittest`).
- The **7 laws** and the **non-goals** (see `README.md` / `AGENTS.md`) are non-negotiable. A
  proposal that requires Lifeline to *execute* or *train* is out of scope.

## Structure

- `lifeline/` — the package. `tests/` — the suites. `scripts/` — proofs and utilities
  (`acceptance`, `firetest`, `exam`, `mcp_live_test`, `migrate_check`).
- `docs/ARCHITECTURE.md` — the technical design and the *why* (with references to the entries).
- `lifeline/schema.sql` — the Supabase cloud schema (print it with `lifeline schema`).
  `docs/MCP_REMOTE.md` / `docs/DEPLOY.md` — the cloud.
- The previous SDK (rev0) is preserved in **git history** (it's gitignored, not in the tree) —
  reference, not executed.

## Development setup

```bash
pip install -e .          # installs lifeline + lifeline-mcp (editable)
pip install -e ".[cloud]" # optional: cloud mode (Supabase)
```
