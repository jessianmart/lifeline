# Integration — closing the loop without a human

Lifeline has two sides, and the AI drives both:

- **Read on connect** → MCP resource `lifeline://project/context` (or `python -m lifeline context`).
- **Write while working** → MCP tools `lifeline_append` / `lifeline_recontextualize` (or `python -m lifeline log`).

## MCP client (any of them)

Point the client at the stdio server:

```
LIFELINE_DB=.lifeline/ledger.db python -m lifeline.mcp_server
```

- **Resource:** `lifeline://project/context` — read it when opening the session.
- **Tools:** `lifeline_append(kind, summary, body, …)`, `lifeline_recontextualize(parent_id, summary, body, …)`.
- **Server command:** `lifeline-mcp` (after `pip install -e .`) or `python -m lifeline.mcp_server` (from the repo root).

## Per-client snippets (copy-and-paste)

**Claude Code** — already reads the project's `.mcp.json` **automatically**. Without it: `claude mcp add lifeline -- lifeline-mcp`.

**Cursor** — `.cursor/mcp.json` (at the project root):
```json
{ "mcpServers": { "lifeline": { "command": "lifeline-mcp", "env": { "LIFELINE_DB": ".lifeline/ledger.db" } } } }
```

**Claude Desktop** — `claude_desktop_config.json` (use an ABSOLUTE path — the cwd differs):
```json
{ "mcpServers": { "lifeline": { "command": "lifeline-mcp", "env": { "LIFELINE_DB": "C:/path/to/project/.lifeline/ledger.db" } } } }
```

**Gemini CLI** — `~/.gemini/settings.json`:
```json
{ "mcpServers": { "lifeline": { "command": "lifeline-mcp", "env": { "LIFELINE_DB": ".lifeline/ledger.db" } } } }
```

> WEB chat apps (claude.ai, ChatGPT) do **not** belong here — they require a remote server + OAuth
> (see `docs/MCP_REMOTE.md`). These snippets are for dev/CLI/IDE clients (stdio, local).

## Auto-connect in Claude Code (SessionStart hook)

Inject the context at the start of each session via the project's `.claude/settings.json`
(the hook's stdout enters the context). Example — adjust to your version's hook schema:

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "python -m lifeline context" } ] }
    ]
  }
}
```

Without a hook, the minimal convention (in CLAUDE.md) is: **on opening, run `python -m lifeline context`
and read it before acting.** When making any decision/feature/fix, append — that way the next AI
(or you tomorrow) connects and already knows.
