# PRD — Lifeline

> Runtime de contexto para desenvolvimento com IA. O projeto carrega a própria
> linha de vida do raciocínio para que qualquer IA conecte e **já saiba**.
>
> As decisões vivas e o *porquê* de cada uma estão em [`LIFELINE.md`](LIFELINE.md).
> Este PRD é o retrato estável; a LIFELINE é a verdade append-only.

## 1. Problema

Assistentes de IA são stateless entre sessões. A cada nova sessão/agente/provider,
o humano vira o barramento de contexto — reexplicando decisões que já existiam. A
correção ingênua (um log markdown vivo) funciona mas cresce sem limite e estoura a
janela. Ferramentas de "memória" guardam texto/vetores sem proveniência → recall
alucinado.

## 2. Norte

**Tempo-até-Contexto (TTC) → 0.** Teste de aceitação: *uma IA nova conecta, sem
humano no meio, e responde corretamente o quê / por quê / o que está decidido / o
que vem a seguir.* Hoje = não. Pronto = sim, em segundos.

## 3. Usuários

v1: dev solo + seus assistentes de IA, local-first. Depois: time com múltiplos
humanos + IAs num contexto compartilhado.

## 4. Goals / Non-goals

**Goals:** contexto local-first portátil no repo; cadeia append-only,
content-addressed, imutável, auditável; memória ancorada à proveniência;
multi-provider nativo; MCP-native; escala além da janela (ranking+compressão+
retrieval); híbrido OSS local + nuvem paga.

**Non-goals:** NÃO é orquestrador/sandbox de agentes; NÃO é workflow engine; NÃO
substitui git; v1 NÃO é multi-usuário em tempo real (DAG já prepara, UX de merge é
depois).

## 5. Modelo de domínio

- **Entry (evento):** unidade atômica. `id = sha256(conteúdo + pais)`, determinístico
  (`ts`/`dedup_key` fora do hash). Campos: id, ts, autoria (human | agent+provider+
  model), kind, summary (o quê), body (o porquê), parents (DAG), hash.
- **Âncora de proveniência (Invariante #1):** todo derivado carrega o hash da
  origem. Sem âncora → não entra.
- **3 camadas de memória:** (1) ledger episódico — DAG hasheado imutável, fonte de
  verdade; (2) estado operacional — verdade atual reduzida via reducers (status é
  projeção, não FSM); (3) recall semântico — embeddings ancorados.
- **Montagem de contexto:** dado cursor/consulta, produz payload ranqueado,
  comprimido e no formato do provider, dentro de um budget.
- **Recontextualização:** ação humana de 1ª classe; correções são entradas novas
  ancoradas.

## 6. Capacidades

C1 Captura (anexar ancorado) · C2 Integridade (verify chain, drift, dedup) · C3
Redução de estado (reducers; status como projeção) · C4 Recall (embed+busca
ancorada) · C5 Montagem (rank+comprime+render por provider) · C6 MCP (resources de
contexto+ledger; tools append/recontextualize) · C7 Projeções (timeline, "por quê",
summaries) · C8 Snapshot/sync.

**Segmentação funcional (de C5):** fragmentos taguados por papel (procedural /
constraint / objetivo / grounding / semântico), guardados planos e ancorados; o
retrieval escolhe as dimensões que a *query* precisa. Camada derivada, nunca a
fonte. (Sem "Ramo Dourado" write-time.)

## 7. Leis

Ver [`CLAUDE.md`](CLAUDE.md) e o protocolo da [`LIFELINE.md`](LIFELINE.md). Resumo:
âncora imutável · append-only · content-addressing determinístico · agnóstico de
provider / entrega por provider · porquê > quê · budget first-class · MCP-native.

## 8. Arquitetura

Ports & adapters. Core depende só de abstrações (`EventStore`, `VectorIndex`,
`LLMAdapter`). Local (OSS): SQLite WAL, vetor cosseno in-process, projeção markdown,
MCP stdio. Nuvem (paga): Postgres/Supabase + pgvector + Redis Streams + MCP
hospedado — trocável sem tocar no core.

## 9. Interfaces

- **SDK:** `append()`, `assemble()`, `recall()`, `verify()`, `snapshot()`.
- **MCP:** `lifeline://project/context` (montado), `lifeline://project/ledger`;
  tools `lifeline.append`, `lifeline.recontextualize`, `lifeline.why`.
- **CLI:** `init`, `log`, `context`, `verify`, `timeline`.

## 10. Não-funcionais

TTC: contexto montado em segundos, budget de tokens fixo **independente do tamanho
do ledger**. Integridade O(n), tamper-evident. Portável (arquivo único). Privacidade
na nuvem: tenant isolation, cripto at-rest, opt-in do que sai da máquina.
Determinismo de hashing entre máquinas.

## 11. Híbrido (OSS vs pago)

OSS local: o core inteiro (laço single-user grátis). Pago (nuvem): sync entre
dispositivos/time, retrieval em escala, merge multi-usuário, embeddings
gerenciados, dashboards. Valor = colaboração + escala + zero-ops, não trancar o core.

## 12. Roadmap

- **M0 Bootstrap (✔):** repo limpo, LIFELINE semeada (#0001 + decisões), leis,
  ferramenta de hash verificável.
- **M1 O laço (MVP, local):** captura ancorada → ledger (DAG determinístico) →
  redução de estado → montagem → resource MCP de contexto. Dogfood: ingere a própria
  LIFELINE; o teste de aceitação roda contra o próprio repo.
- **M2 Recall + projeções:** busca semântica ancorada; projeção "por quê"; summaries.
- **M3 Seam de nuvem:** adapter Supabase + pgvector + sync.
- **M4 Multi-usuário:** merge de DAG real + recontextualização + conflito.

## 13. Riscos

Fricção de captura (quem escreve, quando — precisa de baixo atrito sem firehose) ·
fidelidade da compressão (não jogar fora o porquê) · determinismo vs riqueza ·
privacidade na nuvem · ovo-e-galinha do dogfooding (ponte: markdown agora → ingestão
no M1).
