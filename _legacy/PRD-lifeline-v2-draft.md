# PRD — Lifeline (v0 draft)

> Runtime de contexto para desenvolvimento com IA. O projeto carrega a própria
> linha de vida do raciocínio — o quê foi feito, por quê, o que está decidido,
> o que vem a seguir — para que qualquer IA, de qualquer provider, em qualquer
> sessão, conecte e **já saiba**, sem humano reexplicando.

Status: draft para reação. Este documento é, ele mesmo, candidato à entrada #0001
da LIFELINE do novo projeto.

---

## 1. O problema

Assistentes de IA são **stateless entre sessões**. Cada nova sessão, agente ou
provider começa do zero, e o humano vira o barramento de contexto — reexplicando
decisões, restrições e histórico que já existiam.

A correção ingênua — um log markdown vivo (a `LIFELINE.md`) — funciona lindamente
até não funcionar: cresce sem limite (na instância comprovada: 159 entradas /
17.511 linhas / 1.3 MB, nunca rotacionada) e estoura a janela de contexto. Sem
ranking, sem retrieval, sem compressão.

Ferramentas de "memória" existentes guardam texto/vetores mas **não impõem
proveniência** → recall alucinado. Não há cadeia imutável e auditável ligando "o
que a IA acredita" a "o que de fato aconteceu".

## 2. Visão e Norte

**Visão:** o projeto carrega a própria memória viva — uma linha de vida de
raciocínio — que qualquer IA conecta via MCP e reconstrói contexto de trabalho na
hora.

**Métrica-norte: Tempo-até-Contexto (TTC)** de um agente novo → ~zero.
Operacionalizado como **teste de aceitação**:

> Uma IA nova conecta, sem humano no meio, e responde corretamente:
> **o quê / por quê / o que está decidido / o que vem a seguir?**

Hoje = não (horas de leitura + explicação). Pronto = sim, em segundos.

## 3. Usuários

- **v1 (primário):** dev solo + seus assistentes de IA (Claude Code, Cursor, etc.)
  em um projeto, local-first.
- **Depois:** time com múltiplos humanos + múltiplas IAs num contexto compartilhado.
- O "usuário" é bilateral: o **humano** (autoriza, corrige, recontextualiza) e a
  **IA** (consome e anexa, sempre ancorada).

## 4. Goals / Non-goals

**Goals**
- Contexto local-first, portátil, que vive no repo.
- Cadeia append-only, content-addressed, imutável, auditável.
- Memória ancorada à proveniência (invariante anti-alucinação).
- Multi-provider nativo (ledger agnóstico; saída no formato do provider).
- MCP-native: a interface primária da IA para ler/escrever contexto.
- Escala além da janela: ranking + compressão + retrieval → contexto nunca estoura.
- Híbrido: core OSS local; nuvem paga opcional (sync, time, retrieval hospedado).

**Non-goals (explícitos)**
- NÃO é plataforma de execução/orquestração de agentes nem runner de sandbox.
- NÃO é workflow engine / máquina de estados de execução.
- NÃO substitui o git (registra raciocínio, não conteúdo de arquivo).
- v1 NÃO é multi-usuário em tempo real (a topologia DAG já prepara, mas a UX de
  merge fica para depois).

## 5. Conceitos centrais (modelo de domínio)

- **Entry (evento)** — a unidade atômica. Content-addressed: `hash = f(conteúdo,
  pais)`, determinístico em qualquer máquina. Campos: `id`, `ts` (campo, **fora**
  do hash), autoria (`human` | `agent` + `provider` + `model`), `kind` (`decision`
  | `feature` | `fix` | `incident` | `note` | `correction` ...), `summary` (o
  *quê*), `body` (o *porquê*), `parents` (links do DAG), `hash`.
- **Âncora de proveniência (Invariante #1)** — todo item de memória derivado
  carrega o(s) hash(es) do(s) evento(s) de onde veio. Sem âncora → não entra. É a
  espinha anti-alucinação.
- **As 3 camadas de memória:**
  1. **Ledger (episódico)** — DAG hasheado imutável. Fonte de verdade.
  2. **Estado (operacional)** — verdade atual consolidada, reduzida do ledger,
     ancorada. *Status é projeção de reducer, não FSM.*
  3. **Recall (semântico)** — embeddings p/ recuperação associativa, cada
     resultado ancorado de volta ao ledger.
- **Montagem de contexto** — dado um cursor/consulta, produz um payload ranqueado,
  comprimido e no formato do provider, dentro de um budget.
- **Recontextualização** — ação humana de primeira classe: autorizar/corrigir/
  repriorizar contexto; correções são **novas entradas ancoradas** (append-only),
  nunca edição.

## 6. Capacidades funcionais

- **C1 Captura** — anexar entradas (humano + agente); validar schema +
  proveniência; selar determinístico; linkar DAG.
- **C2 Integridade** — verificar cadeia (tamper detection); detectar drift causal;
  dedup por content-address.
- **C3 Redução de estado** — reduzir ledger → estado consolidado via reducers;
  status como projeção.
- **C4 Recall** — embeddar + indexar entradas; busca semântica devolve resultados
  ancorados.
- **C5 Montagem** — ranquear (recência / causalidade / falha / prioridade do
  usuário) + comprimir (colapsar loops, budget) + renderizar por provider.
- **C6 Superfície MCP** — resources para ler contexto montado + ledger cru; tools
  para anexar + recontextualizar.
- **C7 Projeções** — visões humanas (timeline markdown, summaries, "por que
  decidimos X").
- **C8 Snapshot/sync** — checkpoint comprimido portátil; (nuvem) sync entre nós.

## 7. Leis / invariantes (a constituição do projeto)

1. **Nenhuma memória sem âncora imutável.**
2. **Append-only**; correções são novas entradas referenciando o hash anterior.
3. **Content-addressing determinístico** (mesmo conteúdo+pais → mesmo id, em
   qualquer nó).
4. **Storage agnóstico de provider; entrega no formato do provider.**
5. **O *porquê* pesa mais que o *quê*** em toda entrada.
6. **Budget é first-class** — contexto cabe na janela; truncamento é explícito,
   nunca silencioso.
7. **MCP-native** — a interface da IA é a superfície do produto, não um apêndice.

## 8. Arquitetura (local-first, com seam para nuvem)

Ports & adapters. O core depende só de abstrações: `EventStore`, `VectorIndex`,
`LLMAdapter`.

- **Local (OSS):** SQLite (WAL), vetor in-process (cosseno), projeção markdown,
  MCP stdio.
- **Nuvem (paga):** Postgres/Supabase (mesma port) + pgvector (recall) + Redis
  Streams (sync) + MCP hospedado. Trocável sem tocar no core.

Árvore de pacote = as 3 camadas + montagem + interfaces (núcleo limpo, ~30
arquivos).

## 9. Interfaces

- **SDK (Python):** `append()`, `assemble()`, `recall()`, `verify()`, `snapshot()`.
- **MCP:** resource `lifeline://project/context` (montado), `lifeline://project/ledger`
  (cru); tools `lifeline.append`, `lifeline.recontextualize`, `lifeline.why`.
- **CLI:** `init`, `log` (anexar), `context` (imprime montado), `verify`, `timeline`.

## 10. Requisitos não-funcionais

- **TTC:** contexto montado para um agente que conecta em < poucos segundos, dentro
  de um budget de tokens fixo **independente do tamanho do ledger** (resolve o
  problema do 1.3 MB).
- **Integridade:** verificação de cadeia O(n); tamper-evident.
- **Portabilidade:** arquivo único local; export/import em um comando.
- **Privacidade (nuvem):** isolamento por tenant, cripto at-rest, opt-in explícito
  do que sai da máquina. (Contexto = raciocínio sobre código + possíveis segredos →
  confiança é a questão nº1 da nuvem.)
- **Determinismo:** hashing reproduzível entre máquinas/SOs.

## 11. Fronteira do modelo híbrido (OSS vs pago)

- **OSS local:** o core inteiro — captura, integridade, 3 camadas, montagem, MCP,
  CLI, vetor local. O laço single-user é grátis.
- **Nuvem paga:** sync entre dispositivos/time, retrieval hospedado em escala,
  merge multi-usuário, embeddings gerenciados, dashboards. Valor = colaboração +
  escala + zero-ops, **não** trancar o core.

## 12. Roadmap / milestones

- **M0 — Bootstrap:** repo limpo; `LIFELINE.md` semeada com as decisões de hoje
  (#0001 bootstrap + entradas `decision`); as leis; o teste de aceitação como doc.
- **M1 — O laço (MVP, single-user, local):** captura (entrada ancorada) → ledger
  (DAG determinístico) → redução de estado → montagem (rank+comprime) → resource
  MCP de contexto. **Dogfood:** ingere a própria `LIFELINE.md` do projeto; o teste
  de aceitação roda contra o próprio projeto.
- **M2 — Recall + projeções:** busca semântica ancorada; projeção "por quê";
  summaries.
- **M3 — Seam de nuvem:** adapter Postgres/Supabase + pgvector + sync de snapshot.
- **M4 — Multi-usuário:** semântica de merge de DAG de verdade + UX de
  recontextualização + superfície de conflito.

## 13. Critério de sucesso / aceitação

O teste de aceitação passa contra o **próprio repo do Lifeline**: um agente novo,
via MCP, responde o quê/por quê/decidido/próximo corretamente, em segundos, com
citações (âncoras) — sem humano. TTC vira um benchmark medido em CI.

## 14. Riscos / questões abertas

- **Fricção de captura:** quem escreve as entradas, e quando? (auto-captura do
  agente vs disciplina humana) → o "entry contract" híbrido precisa de um caminho
  de captura de baixo atrito, senão não é usado. A rev0 funcionou porque a
  disciplina se manteve — dá pra automatizar sem virar firehose?
- **Fidelidade da compressão:** ranking/compressão não pode descartar o *porquê*
  que sustenta a decisão.
- **Determinismo vs riqueza:** content-addressing exige disciplina de
  canonicalização.
- **Modelo de privacidade da nuvem.**
- **Ovo-e-galinha do dogfooding** (ponte: markdown agora → ingestão estruturada no
  M1).

---

### Apêndice — o que NÃO vem do SDK atual

Cortado: `runtime/*` (sandbox, scheduler, process, **FSM**, policies, resources),
`devos/` (swarm), stubs Redis/NATS, os 12 `verify_*`, ~25 arquivos vazios.
Transplantado quase como está: vetor cosseno, compressão (collapse), snapshot zlib,
mecânica do SQLite (WAL/edges/dedup/DLQ), bus local (DLQ+fallback), projeção
markdown, adapter Gemini, cache de contexto, profiler. Reescrito na raiz: modelo de
evento (schema da rev0, content-addressed determinístico), status como reducer, o
resource MCP de contexto.
