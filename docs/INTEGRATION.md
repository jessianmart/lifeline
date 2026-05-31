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
