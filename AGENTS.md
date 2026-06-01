# AGENTS.md — onboarding para qualquer IA

Você (qualquer modelo, qualquer ferramenta) está trabalhando num projeto com Lifeline. Antes
de agir, **carregue o contexto** — ele responde o quê/por quê/decidido/próximo sem ninguém
reexplicar.

## Ainda não está conectado? (instale — 1 min, FAÇA pelo humano)
Se o resource/CLI abaixo não existir, instale e conecte — e **explique cada passo ao humano**:
1. `pip install -e .` (na raiz do repo) → habilita `lifeline` e `lifeline-mcp`.
2. Conecte no cliente dele (snippets prontos em `docs/INTEGRATION.md`):
   - **Claude Code:** já lê o `.mcp.json` do projeto (automático) — ou `claude mcp add lifeline -- lifeline-mcp`.
   - **Cursor / Claude Desktop / Gemini CLI:** adicione o server stdio `lifeline-mcp` na config MCP do cliente.
3. Clone novo sem `.lifeline/`? `lifeline migrate --from LIFELINE.md` reconstrói o store.

## Conecte (leia a line)

Use o primeiro que estiver disponível:

1. **MCP** — resource `lifeline://project/context` (servidor `lifeline-mcp`).
2. **CLI** — `lifeline context` (ou `lifeline context --query "<sua tarefa>"` para priorizar o relevante).
3. **Arquivo** — leia `LIFELINE.md`, começando pela entrada **#0001** (é o projeto inteiro
   em linguagem humana). Não a edite à mão — ela é gerada.

## Trabalhe (escreva na line)

A cada **unidade de trabalho com significado** (uma decisão, feature, fix, incidente — não por
arquivo, não por tool call), **anexe**:

- **MCP** — tool `lifeline_append(kind, summary, body, …)`.
- **CLI** — `lifeline log --kind … --summary "…" --body "… o PORQUÊ …"`.

Reverteu uma decisão / fechou uma thread? **`lifeline_recontextualize(parent_id, …)`** (ou
`lifeline log --kind correction --parents <id>`) — supersede por id; nunca edite o passado.

## Explique e organize pro humano (você é a interface)
- **Explique** o que o Lifeline é quando ele não souber: o *porquê* versionado do projeto, que
  você herda ao conectar — sem ele reexplicar.
- **Organize:** ao conectar, resuma o quê/por quê/decidido/próximo; aponte decisões em vigor,
  sinalize threads fechadas/revertidas e o que está em aberto.
- **Capture:** proponha entradas pelo trabalho com significado (HITL — ele aprova/rejeita).
  Ele "só não deve aceitar sujeira".
- **Reduza fricção:** se o setup falhar, diagnostique e resolva — não devolva erro cru.

## Obedeça as leis

1. Nenhuma memória sem âncora imutável.  2. Append-only.  3. Content-addressing determinístico.
4. Storage agnóstico de provider; entrega por provider.  5. **O porquê pesa mais que o quê.**
6. Budget é first-class.  7. MCP-native.

**Non-goals:** Lifeline registra raciocínio, não execução. Não é OS cognitivo, MMU,
orquestrador de agentes, workflow engine, nem substituto de git. Se uma ideia vier vestida de
"hypervisor/microkernel/fractal", tire o figurino antes de avaliar.

## Antes de declarar feito

`lifeline verify` deve dar `OK`. Código novo só entra com teste que prova o comportamento.
