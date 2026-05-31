# Contribuindo com o Lifeline

A regra é a constituição do projeto: **se você mexeu de forma significativa, anexe na line.**
Humanos e agentes obedecem igual.

## O fluxo

1. **Conecte:** `lifeline context` (ou leia `LIFELINE.md`, começando pela #0001).
2. **Faça o trabalho** — uma unidade coerente por vez.
3. **Anexe o *porquê*:**
   ```bash
   lifeline log --kind decision --summary "≤200 chars: o quê" --body "o PORQUÊ (pesa mais)"
   ```
   `kind ∈ {bootstrap, decision, feature, fix, incident, milestone, release, note, open, correction}`.
   - Reverter/fechar algo: `lifeline log --kind correction --parents <id> --summary "…"`.
4. **Verifique:** `lifeline verify` deve dar `OK`.

> O store (`.lifeline/ledger.db`) é a fonte de verdade; a `LIFELINE.md` é **gerada** e
> **não deve ser editada à mão** — ela se regenera a cada `log`.

## As regras de uma boa entrada

- **Uma entrada por unidade de trabalho com significado** — não por arquivo, não por tool call.
- **O *porquê* > o *quê*** (Lei #5). O `summary` diz o quê; o `body` diz por quê, e é o que
  tem valor pra próxima IA.
- **Append-only** (Lei #2): nunca edite o passado; corrija com uma entrada nova.

## Quality gate

Antes de declarar qualquer trabalho feito:

```bash
# da pasta v2/
for t in entry store state context projection cli mcp recall; do python tests/test_$t.py; done
lifeline verify
```

- Código novo só entra **com teste que prova o comportamento** (TDD-friendly; os testes são
  dependency-free, `unittest`).
- As **7 leis** e os **non-goals** (ver `README.md` / `AGENTS.md`) são inegociáveis. Uma
  proposta que exige o Lifeline *executar* ou *treinar* está fora de escopo.

## Estrutura

- `lifeline/` — o pacote. `tests/` — as suítes. `scripts/` — provas e utilitários
  (`acceptance`, `firetest`, `exam`, `mcp_live_test`, `migrate_check`).
- `docs/ARCHITECTURE.md` — o desenho técnico e o *porquê* (com referências às entradas).
- O SDK anterior está em `../_legacy/` — referência, não executado.

## Setup de desenvolvimento

```bash
pip install -e .          # instala lifeline + lifeline-mcp (editável)
```
