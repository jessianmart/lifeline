# CLAUDE.md — leis do projeto Lifeline

Você (humano ou agente) está trabalhando no **Lifeline**. Antes de qualquer coisa:
**leia `LIFELINE.md`, começando pela entrada #0001.** Ela é o projeto inteiro em
linguagem humana. O *porquê* de cada decisão está nas entradas seguintes.

## O que o Lifeline é

Uma runtime de contexto: o projeto guarda *por que* ele é o que é, e qualquer mente
que conecta herda esse porquê na hora — sem ninguém reexplicar. Sucesso = uma IA
nova conecta, sem humano no meio, e responde o quê/por quê/decidido/próximo, em
segundos (Tempo-até-Contexto → 0).

## O loop (faça os dois lados)

- **Ao CONECTAR:** carregue o contexto antes de agir — `python -m lifeline context`
  (ou o resource MCP `lifeline://project/context`). É a verdade atual montada.
- **Ao TRABALHAR:** a cada decisão/feature/fix/incidente, **anexe** — `python -m lifeline
  log …` (ou a tool MCP `lifeline_append`). Reverteu uma decisão ou fechou uma thread?
  `lifeline_recontextualize` (supersede por id). Assim a próxima IA já sabe.

Integração (hook de auto-connect + config MCP): ver [`docs/INTEGRATION.md`](docs/INTEGRATION.md).

## As 7 leis (inegociáveis)

1. **Nenhuma memória sem âncora imutável.** Todo item de contexto carrega o hash do
   evento de origem. É a espinha anti-alucinação.
2. **Append-only.** Nunca edite o passado; correção é entrada nova referenciando o
   hash anterior.
3. **Content-addressing determinístico.** `id = sha256(conteúdo + pais)`; `ts` e
   `dedup_key` ficam FORA do hash. Mesmo conteúdo → mesmo id em qualquer máquina.
4. **Storage agnóstico de provider; entrega no formato do provider.**
5. **O *porquê* pesa mais que o *quê*.**
6. **Budget é first-class.** Contexto cabe na janela; truncamento é explícito.
7. **MCP-native.** A interface da IA é a superfície do produto.

## Non-goals (não construa isto)

NÃO é OS cognitivo, MMU, orquestrador/sandbox de agentes, workflow engine, nem
substituto de git. Registra raciocínio, não execução. Se uma ideia vier vestida de
"hypervisor/microkernel/fractal/opcode", tire o figurino antes de avaliar.

## A regra que todos obedecem

Se você mexeu no projeto de forma significativa, **anexe uma entrada** — o store
(`.lifeline/ledger.db`) é a fonte de verdade e a `LIFELINE.md` é gerada a partir dele:

```
python -m lifeline log --kind decision --summary "…" --body "… o porquê …"
python -m lifeline verify     # confere a integridade (deve dar OK)
```

NÃO edite a `LIFELINE.md` à mão — ela se regenera a cada `log`. Se o `.lifeline/` não
existir (clone novo), reconstrua: `python -m lifeline migrate --from LIFELINE.md`.

Uma entrada por unidade de trabalho com significado — não por arquivo, não por tool
call. Diga o *porquê*.

## Qualidade

Código novo só entra com teste que prova o comportamento. A cadeia da LIFELINE deve
verificar (`OK`) antes de declarar qualquer trabalho feito.
