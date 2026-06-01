# Integração — fechando o loop sem humano

O Lifeline tem dois lados, e a IA dirige os dois:

- **Ler ao conectar** → resource MCP `lifeline://project/context` (ou `python -m lifeline context`).
- **Escrever ao trabalhar** → tools MCP `lifeline_append` / `lifeline_recontextualize` (ou `python -m lifeline log`).

## Cliente MCP (qualquer um)

Aponte o cliente para o servidor stdio:

```
LIFELINE_DB=.lifeline/ledger.db python -m lifeline.mcp_server
```

- **Resource:** `lifeline://project/context` — leia ao abrir a sessão.
- **Tools:** `lifeline_append(kind, summary, body, …)`, `lifeline_recontextualize(parent_id, summary, body, …)`.
- **Comando do server:** `lifeline-mcp` (após `pip install -e .`) ou `python -m lifeline.mcp_server` (da raiz do repo).

## Snippets por-cliente (copia-e-cola)

**Claude Code** — já lê o `.mcp.json` do projeto **automaticamente**. Sem ele: `claude mcp add lifeline -- lifeline-mcp`.

**Cursor** — `.cursor/mcp.json` (na raiz do projeto):
```json
{ "mcpServers": { "lifeline": { "command": "lifeline-mcp", "env": { "LIFELINE_DB": ".lifeline/ledger.db" } } } }
```

**Claude Desktop** — `claude_desktop_config.json` (use caminho ABSOLUTO — o cwd difere):
```json
{ "mcpServers": { "lifeline": { "command": "lifeline-mcp", "env": { "LIFELINE_DB": "C:/caminho/do/projeto/.lifeline/ledger.db" } } } }
```

**Gemini CLI** — `~/.gemini/settings.json`:
```json
{ "mcpServers": { "lifeline": { "command": "lifeline-mcp", "env": { "LIFELINE_DB": ".lifeline/ledger.db" } } } }
```

> Apps de chat WEB (claude.ai, ChatGPT) **não** entram aqui — exigem servidor remoto + OAuth
> (ver `docs/MCP_REMOTE.md`). Estes snippets são pros clientes de dev/CLI/IDE (stdio, local).

## Auto-connect no Claude Code (hook de SessionStart)

Injete o contexto no início de cada sessão via `.claude/settings.json` do projeto
(o stdout do hook entra no contexto). Exemplo — ajuste ao schema de hooks da sua versão:

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "python -m lifeline context" } ] }
    ]
  }
}
```

Sem hook, a convenção mínima (no CLAUDE.md) é: **ao abrir, rode `python -m lifeline context`
e leia antes de agir.** Ao tomar qualquer decisão/feature/fix, anexe — assim a próxima IA
(ou você amanhã) conecta e já sabe.
