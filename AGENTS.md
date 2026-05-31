# AGENTS.md — onboarding para qualquer IA

Você (qualquer modelo, qualquer ferramenta) está trabalhando num projeto com Lifeline. Antes
de agir, **carregue o contexto** — ele responde o quê/por quê/decidido/próximo sem ninguém
reexplicar.

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

## Obedeça as leis

1. Nenhuma memória sem âncora imutável.  2. Append-only.  3. Content-addressing determinístico.
4. Storage agnóstico de provider; entrega por provider.  5. **O porquê pesa mais que o quê.**
6. Budget é first-class.  7. MCP-native.

**Non-goals:** Lifeline registra raciocínio, não execução. Não é OS cognitivo, MMU,
orquestrador de agentes, workflow engine, nem substituto de git. Se uma ideia vier vestida de
"hypervisor/microkernel/fractal", tire o figurino antes de avaliar.

## Antes de declarar feito

`lifeline verify` deve dar `OK`. Código novo só entra com teste que prova o comportamento.
