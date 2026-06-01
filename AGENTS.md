# AGENTS.md — onboarding for any AI

You (any model, any tool) are working on a project that uses Lifeline. Before acting,
**load the context** — it answers what/why/decided/next with no one re-explaining.

## Not connected yet? (install — 1 min, DO IT for the human)
If the resource/CLI below doesn't exist, install and connect — and **explain each step to the human**:
1. `pip install lifeline-context` (or `pip install -e .` from the repo root) → enables `lifeline` and `lifeline-mcp`.
2. Connect it in their client (ready-made snippets in `docs/INTEGRATION.md`):
   - **Claude Code:** already reads the project's `.mcp.json` (automatic) — or `claude mcp add lifeline -- lifeline-mcp`.
   - **Cursor / Claude Desktop / Gemini CLI:** add the stdio server `lifeline-mcp` to that client's MCP config.
3. Fresh clone without `.lifeline/`? `lifeline migrate --from LIFELINE.md` rebuilds the store.

## Connect (read the line)
Use whichever is available first:
1. **MCP** — resource `lifeline://project/context` (server `lifeline-mcp`).
2. **CLI** — `lifeline context` (or `lifeline context --query "<your task>"` to prioritize the relevant).
3. **File** — read `LIFELINE.md`, starting at entry **#0001** (the whole project in human language). Don't hand-edit it — it's generated.

## Work (write to the line)
On each **meaningful unit of work** (a decision, feature, fix, incident — not per file, not per tool call), **append**:
- **MCP** — tool `lifeline_append(kind, summary, body, …)`.
- **CLI** — `lifeline log --kind … --summary "…" --body "… the WHY …"`.

Reversed a decision / closed a thread? **`lifeline_recontextualize(parent_id, …)`** (or
`lifeline log --kind correction --parents <id>`) — supersede by id; never edit the past.

## Explain and organize for the human (you are the interface)
- **Explain** what Lifeline is when they don't know: the versioned *why* of the project, which
  you inherit on connect — without them re-explaining.
- **Organize:** on connect, summarize what/why/decided/next; point out decisions in force,
  flag closed/reverted threads and what's open.
- **Capture:** propose entries for meaningful work (HITL — they approve/reject). They "just
  shouldn't accept junk."
- **Reduce friction:** if setup fails, diagnose and fix it — don't hand back a raw error.

## Obey the laws
1. No memory without an immutable anchor.  2. Append-only.  3. Deterministic content-addressing.
4. Provider-agnostic storage; deliver in the provider's format.  5. **The why outweighs the what.**
6. Budget is first-class.  7. MCP-native.

**Non-goals:** Lifeline records reasoning, not execution. It's not a cognitive OS, MMU, agent
orchestrator, workflow engine, or a git replacement. If an idea arrives dressed as
"hypervisor/microkernel/fractal", strip the costume before evaluating it.

## Before declaring done
`lifeline verify` must print `OK`. New code only lands with a test that proves the behavior.
