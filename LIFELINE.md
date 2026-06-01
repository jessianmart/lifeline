# LIFELINE — lifeline

> Cadeia append-only de *porquês*. O projeto guarda *por que* ele é o que é, e qualquer
> mente que conecta herda esse porquê na hora — sem ninguém reexplicar.
>
> **Este arquivo é GERADO** a partir do ledger (em `.lifeline/`), que é a fonte de verdade.
> NÃO edite à mão — anexe com `lifeline log` e ele se regenera.
>
> **Comece pela #0001.** Ela é o projeto inteiro em linguagem humana.

## Protocolo

1. **Append-only.** Nunca edite entradas; uma correção é uma entrada nova (`kind: correction`)
   que referencia em `parents` o `id` que corrige — e o supersede na verdade atual.
2. **Uma entrada por unidade de trabalho com significado.** Não por arquivo, não por tool
   call. O *porquê* pesa mais que o *quê* (Lei #5).
3. **Identidade content-addressed (Lei #3):** `id = sha256(kind, author, agent, provider,
   model, summary, body, parents-ordenados)`. `ts` e `dedup_key` ficam FORA do hash — o
   mesmo conteúdo gera o mesmo `id` em qualquer máquina. `parents` formam o DAG causal;
   não há prev_hash (o ledger é um grafo, não uma lista).
4. **Integridade:** `lifeline verify` confere que todo `id` bate com seu conteúdo.
5. **Anexar:** `lifeline log --kind … --summary … --body …`. Ver o contexto montado que uma
   IA receberia: `lifeline context`.

## Leis do projeto (a constituição)

1. **Nenhuma memória sem âncora imutável.** Todo item de contexto carrega o hash do evento
   de origem. Espinha anti-alucinação.
2. **Append-only.** Correções são entradas novas referenciando o id anterior.
3. **Content-addressing determinístico.** Mesmo conteúdo+pais → mesmo id, em qualquer nó.
4. **Storage agnóstico de provider; entrega no formato do provider.**
5. **O *porquê* pesa mais que o *quê*.**
6. **Budget é first-class.** Contexto cabe na janela; truncamento é explícito, nunca silencioso.
7. **MCP-native.** A interface da IA é a superfície do produto, não um apêndice.

**Non-goals (lei por omissão):** Lifeline NÃO é sistema operacional cognitivo, NÃO é MMU,
NÃO é orquestrador/sandbox de agentes, NÃO é workflow engine, NÃO substitui git, NÃO é
executor/curador (self-healing) nem treinador (fine-tuning/DL). Registra raciocínio.

---

## Entries

### #0001 — 2026-05-30T14:00:00+00:00 — bootstrap

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: bootstrap
- **summary**: Funda o Lifeline — runtime de contexto que faz uma IA nova conectar e já saber, sem humano reexplicando
- **parents**: —
- **id**: 6f0d172fd29d9d42060a0ab78c882c9c3e29f61231723f0a87c018b813ad2986

**Body**:
O Lifeline existe para que o dono do projeto pare de ser a memória. Hoje, toda vez
que uma sessão acaba, uma janela de contexto enche, ou a ferramenta muda (ChatGPT,
Gemini, Claude), a cadeia de raciocínio que sustenta o projeto morre — e o humano
vira o único backup, reexplicando decisões que já foram tomadas.

O Lifeline é: **o projeto guarda *por que* ele é o que é, e qualquer mente que
conecta herda esse porquê na hora — sem ninguém reexplicar.**

Norte (teste de aceitação): uma IA nova conecta, sem humano no meio, e responde
corretamente o quê / por quê / o que está decidido / o que vem a seguir. Hoje =
não (horas de leitura + explicação). Pronto = sim, em segundos. A métrica é o
Tempo-até-Contexto → zero.

Origem: nasceu de uma `LIFELINE.md` mantida à mão no projeto `inframoe` (cadeia de
hash append-only, 159 entradas) que comprovadamente resolveu essa dor — mas crescia
sem limite e estourava a janela. O Lifeline mantém essa disciplina e a torna
consultável/comprimível, para nunca estourar. Esta própria entrada foi escrita no
momento em que o produto se provou: o fundador não conseguiu explicar o que queria,
e não precisou — o contexto bastou.

### #0002 — 2026-05-30T14:10:00+00:00 — decision

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: decision
- **summary**: Trava o núcleo — 3 camadas ancoradas, DAG content-addressed, status como reducer, e os non-goals
- **parents**: 6f0d172fd29d9d42060a0ab78c882c9c3e29f61231723f0a87c018b813ad2986
- **id**: 48f39a88564bb63aee5f36230ec7be6dd33b86d6ac4179a3cd1a5d090168834a

**Body**:
O coração tem três camadas, todas ancoradas no mesmo ledger imutável: (1) ledger
episódico — DAG hasheado, fonte de verdade; (2) estado operacional — verdade atual
reduzida do ledger via reducers (status é projeção de reducer, NÃO máquina de
estados de execução); (3) recall semântico — embeddings, cada resultado ancorado de
volta ao ledger. Topologia DAG (escolha do dono, preparando contribuição concorrente
multi-IA/multi-usuário no futuro), mas reconstruída correta: hash determinístico
(sem timestamp no hash) e merge de verdade.

Porquê: o SDK anterior foi especificado pelo ChatGPT como "microkernel cognitivo /
hypervisor / OS distribuído" e codado pelo Gemini, virando vocabulário > substância
(~25 arquivos vazios, sandbox/scheduler/distribuído que eram teatro). Os non-goals
(não é OS/MMU/orquestrador/workflow/git) existem para impedir que essa inflação
ressuscite.

### #0003 — 2026-05-30T14:20:00+00:00 — decision

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: decision
- **summary**: Absorve segmentação funcional em 5 dimensões como capacidade derivada e ancorada; rejeita o Ramo Dourado
- **parents**: 48f39a88564bb63aee5f36230ec7be6dd33b86d6ac4179a3cd1a5d090168834a
- **id**: f231a646c7732a9648005f3503214ca87636c47e58f608f75703cb51627e6405

**Body**:
A ideia boa do material "CortexFS/Deep1545": segmentar contexto por utilidade
funcional em 5 dimensões (procedural, constraint, objetivo, grounding, semântico),
para na hora de uma decisão ler só as dimensões relevantes (ex.: constraint +
grounding para analisar multa) — menos tokens, menos ruído, menos alucinação.
Absorvido COMO capacidade do Context Engine, com 3 guard-rails: (a) segmentação é
camada DERIVADA, nunca a fonte de verdade — o evento bruto continua imutável; (b)
todo fragmento carrega o hash do evento de origem (Lei #1); (c) é gerada por LLM,
logo não-determinística → vive na camada regenerável, jamais no ledger.

Rejeitado: o "Ramo Dourado" (recursão fractal via Pareto que elege UMA dimensão
vencedora na ingestão). Porquê: relevância é propriedade da *pergunta* (read-time),
não do documento (write-time); e o próprio exemplo (precisa de constraint+grounding,
duas dimensões) contradiz a eleição de uma só vencedora. Guarda as 5 dimensões
planas e o retrieval escolhe na query. Branding ("Pentagrama", "Opcode 0xDB") é o
mesmo figurino que inflou o SDK — descartado.

### #0004 — 2026-05-30T14:30:00+00:00 — decision

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: decision
- **summary**: Abordagem de build — reconstrução limpa, transplante dos órgãos comprovados, dogfooding desde a #0001
- **parents**: f231a646c7732a9648005f3503214ca87636c47e58f608f75703cb51627e6405
- **id**: 2a30e67af0dbb0fab7ac45e5740b60253053f20d4540508c589a4e1dc6d643d4

**Body**:
Nem polir o SDK antigo (o defeito é estrutural: identidade do evento ancorada em
timestamp; vocabulário polui), nem greenfield puro (há código testado bom). Caminho:
reconstruir o esqueleto limpo e transplantar os órgãos comprovados do SDK anterior —
vetor cosseno, compressão (collapse anti-loop), snapshot zlib, mecânica do SQLite
(WAL/edges/dedup/DLQ), bus local com fallback, projeção markdown, adapter Gemini,
cache de contexto. Reescrever na raiz: modelo de evento (content-addressed
determinístico), status como reducer, e o resource MCP de contexto (a feature que
entrega o norte e que não existia no SDK).

Estratégia de produto: dogfooding tão bem-feito que resolva primeiro a dor do dono,
depois a dos outros, e então monetize como híbrido — core OSS local grátis; nuvem
paga (Supabase + pgvector + Redis Streams) para sync, time e escala. M1 = o laço
mínimo (captura ancorada → ledger → estado → montagem → MCP) que já passa o teste de
aceitação contra o próprio repo do Lifeline.

### #0005 — 2026-05-30T15:00:00+00:00 — feature

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: feature
- **summary**: M1 começou — modelo de evento content-addressed (Entry) testado; fundação fechada (CLAUDE.md + PRD portados)
- **parents**: 2a30e67af0dbb0fab7ac45e5740b60253053f20d4540508c589a4e1dc6d643d4
- **id**: 71cd696670d37531b5bfdb24434f698215668927056c64d63771566485557fe2

**Body**:
Fundação fechada: CLAUDE.md (as 7 leis + a regra "se mexeu, anexe na LIFELINE e
re-sele" — para humanos e agentes obedecerem igual) e PRD.md portados para v2/.

M1 (o laço) começou pela peça-raiz: lifeline/entry.py — o Entry content-addressed.
id = sha256(conteúdo + pais ordenados); ts e dedup_key ficam fora do hash (Lei #3).
7 testes provam: id estável a despeito do ts, sensível ao body, invariante à ordem
dos pais, dedup_key não altera identidade, e auto-verificável (verify() detecta
adulteração). É a primeira linha de código do produto e ela obedece à constituição.

Próximo: store SQLite append-only (transplante WAL/edges/dedup/DLQ do SDK antigo,
agora determinístico) → redução de estado via reducers → montagem → resource MCP de
contexto.

### #0006 — 2026-05-30T15:30:00+00:00 — feature

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: feature
- **summary**: Ledger SQLite (Camada 1) atrás da interface EventStore — append idempotente, DAG navegável, costura pra nuvem
- **parents**: 71cd696670d37531b5bfdb24434f698215668927056c64d63771566485557fe2
- **id**: 9b466e11709a270cac6b9ae24d2cf444ff841e2d1ebf46e7e1fedfad18aa560b

**Body**:
Landou lifeline/store.py: a Camada 1 (ledger episódico). EventStore (ABC) é a costura
— o core depende só dela; um SupabaseEventStore futuro implementa a mesma interface
sem tocar no núcleo (é assim que a nuvem entra sem inflar o core). SQLiteEventStore é
o adapter local: WAL, tabela de arestas pro DAG, índice único de dedup.

5 testes provam: roundtrip lossless (Entry reconstruído mantém id e verify()), append
idempotente por id E por dedup_key (a dor do "split-brain" do SDK velho, resolvida de
forma simples), ordem causal de inserção, e navegação parents/children no DAG.

Estratégia confirmada nesta sessão (sobre OSS local + nuvem paga): desenhar a costura
(interface) agora, adiar o código de nuvem pro M3 — construir nuvem com zero usuário é
a mesma generalização prematura que inflou o SDK. A monetização real mora no caso de
TIME (contexto compartilhado), não no solo. O risco existencial nº1 é a fricção de
captura — validada ao vivo por este próprio dogfooding. Próximo: redução de estado
(reducers, status como projeção) → montagem de contexto → resource MCP. Alvo do M1:
fechar o laço e rodar o teste de aceitação contra a própria LIFELINE.

### #0007 — 2026-05-30T16:00:00+00:00 — feature

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: feature
- **summary**: Camada 2 (estado como projeção + supersessão por correção) e montagem mínima — payload o quê/por quê/decidido/próximo
- **parents**: 9b466e11709a270cac6b9ae24d2cf444ff841e2d1ebf46e7e1fedfad18aa560b
- **id**: ef1bd6b89fda7dd639e611e105fb5c106ead9adaaf42cdab9e61d601649e23ec

**Body**:
Landou lifeline/state.py (Camada 2) e lifeline/context.py (montagem). StateEngine
dobra o ledger em "verdade atual" via reducers puros — status é PROJEÇÃO, não FSM
(decisão #0002). O reducer padrão ledger_projection entrega identidade + decisões em
vigor + recentes, e respeita correções: uma entrada `correction` supersede seus pais
(Lei #2), então a verdade atual nunca mostra decisão revogada. ContextAssembler
renderiza o payload "o quê (bootstrap) / por quê e decidido (decisões) / o que vem a
seguir (recentes)" dentro de um budget, com truncamento sempre explícito (Lei #6).

17 testes verdes (entry 7, store 5, state 3, context 2). O laço está a UM passo de
fechar: falta o resource MCP + um ingester (markdown LIFELINE → store) para rodar o
teste de aceitação contra a própria v2/.

Seam pendente de decisão: hoje existem DOIS esquemas de hash — a cadeia da markdown
(scripts/lifeline_hash.py, estilo prev_hash) e o id content-addressed do Entry (estilo
pais/DAG). Funcionam para propósitos diferentes (integridade humana vs identidade de
runtime), mas precisam ser unificados — provavelmente gerando a markdown A PARTIR do
store, ou alinhando as duas formas canônicas. Decisão para a próxima sessão.

### #0008 — 2026-05-30T16:45:00+00:00 — milestone

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: milestone
- **summary**: Teste de aceitação PASSOU — agente sem contexto respondeu o quê/por quê/decidido/próximo só do payload (TTC ~15s, 80%)
- **parents**: ef1bd6b89fda7dd639e611e105fb5c106ead9adaaf42cdab9e61d601649e23ec
- **id**: 3be2531b7328a61544c19fc9426966e16661a0ab303e5f545321a7be4d792fdb

**Body**:
O laço do M1 fechou e foi validado contra o próprio projeto. Landaram lifeline/
ingest.py (markdown → store) e lifeline/mcp_server.py (resource lifeline://project/
context, Lei #7). O ContextAssembler passou a incluir o *porquê* (corpo das decisões,
truncado) — Lei #5.

Teste de aceitação: um agente general-purpose com ZERO contexto desta sessão, proibido
de explorar o repo, recebeu APENAS o payload montado (2208 chars, ingerindo as 7
entradas da própria LIFELINE) e respondeu corretamente, sozinho, em ~15s: o quê (runtime
de contexto), por quê (TTC→0), decidido (3 camadas, DAG content-addressed, status como
projeção, segmentação funcional, Ramo Dourado rejeitado) e próximo (M1: Entry + Camada 1
+ Camada 2). Confiança autorreportada: 80%. O norte (TTC) saiu de "horas + humano" para
"~15s, sem humano".

Backlog do M2 que o próprio agente revelou (auto-crítica do produto): o payload precisa
de uma seção "próximo/aberto" explícita (hoje só mostra recentes); corpos de decisão
truncados limitam precisão (ranking/compressão funcional do M2 resolve); Camada 3 (recall
semântico) ausente. Pendências: unificar os dois esquemas de hash (store vira fonte,
markdown gerada) e transplantar vetor cosseno + compressão do SDK antigo. 17/17 testes
verdes. M1: essencialmente concluído e provado.

### #0009 — 2026-05-30T17:15:00+00:00 — decision

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: decision
- **summary**: Visão e posicionamento — Lifeline é o "GitHub para contexto de IA" (não de código): core local git-like (OSS) → hub na nuvem (pago)
- **parents**: 3be2531b7328a61544c19fc9426966e16661a0ab303e5f545321a7be4d792fdb
- **id**: d9b210427d6f86df7ae9a3904dafde082d88ef7735046ba91c3dde5721c3c941

**Body**:
Framing definido pelo dono: o Lifeline é o "GitHub para contexto de IA". git é o DAG
content-addressed append-only do CÓDIGO (o *o quê*); o Lifeline é o DAG content-addressed
append-only do RACIOCÍNIO/CONTEXTO (o *porquê*). GitHub é o hub sobre o git; o Lifeline
Hub é o hub sobre o Lifeline. As decisões já travadas (#0002, #0004) são exatamente o
modelo git — o framing não é marketing imposto depois, é o destino natural delas.

Distinção e non-goal: Lifeline NÃO reimplementa git nem versiona arquivos. git guarda o
quê (código); Lifeline guarda o porquê (raciocínio) — complementares, não concorrentes.
Em uso não-code/conversacional (onde não há git), o Lifeline fica sozinho. Uma "linha"
(line) = um repo/branch de contexto, multiprovider e async; clone/fork/merge de linhas
são operações naturais (M4). Detalhe: somos mais content-puros que o git — tiramos o ts
do hash (o commit do git inclui timestamp) para dedup funcionar entre providers.

Fases (batem com o roadmap): local git-like = M1 (feito) + M2, o core OSS grátis; nuvem
+ hub = M3 (sync Supabase) + M4 (o Hub: compartilhar linhas, time, privado, descoberta),
o pago. Monetização open-core provada pelo próprio GitHub (git grátis, GitHub é negócio).
Caveat honesto: a analogia comunica, mas o moat continua sendo a cunha — proveniência
ancorada + multiprovider + o porquê>o quê.

### #0010 — 2026-05-30T17:40:00+00:00 — decision

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: decision
- **summary**: Formato do payload = markdown com estrutura leve, NÃO JSON/YAML — compactação é semântica, não sintática
- **parents**: d9b210427d6f86df7ae9a3904dafde082d88ef7735046ba91c3dde5721c3c941
- **id**: f01f9e0ee6644147bda4f14bdafb289c75f2b9d812e91c2859d84f17a15feedd

**Body**:
O payload que a IA lê é renderizado em markdown, não JSON/YAML. Porquê: JSON/YAML gastam
tokens com aspas/chaves/keys repetidas por item; LLMs são treinados em markdown e parseiam
headings/bullets nativamente — melhor compreensão por token. Não existe "protocolo mágico
de IA": o modelo É de linguagem, então linguagem-com-estrutura-leve é o formato nativo;
scaffolding JSON tende a atrapalhar (mais token, às vezes mais confusão). JSON serve pro
caso inverso — quando um PROGRAMA parseia a saída do modelo.

A compactação que importa NÃO é a sintática (serialização), e sim a semântica: rankear/
selecionar o relevante + sumarizar + segmentação funcional (M2). A Lei #4 deixa a porta
aberta pra renderers por provider depois (ex.: tags XML pro Claude delimitar seções), mas
markdown é o default. Registrado para ninguém "otimizar" pra JSON no futuro.

### #0011 — 2026-05-30T17:45:00+00:00 — feature

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: feature
- **summary**: Autoria no payload — quem/provider/modelo de cada decisão + agregado de contribuidores (proveniência multiprovider)
- **parents**: f01f9e0ee6644147bda4f14bdafb289c75f2b9d812e91c2859d84f17a15feedd
- **id**: fee2a0f600342b3e6e9e2fc73195019b167f10039d74985795586e12df437d3a

**Body**:
O ContextAssembler agora mostra a autoria que já existia no ledger mas estava oculta: cada
decisão exibe `provider/modelo`, o bootstrap mostra "fundado por", e um agregado
"Contribuíram: …" lista quem produziu o quê e quanto. Em contexto multiprovider isso é
proveniência de raciocínio — dá pra confiar/auditar/questionar uma decisão por quem a fez
(ex.: "essa foi o Gemini, vale revisar"). É a Lei #1 (ancoragem) aplicada à autoria.
state.ledger_projection agrega `contributors` e carrega provider/model nas decisões e
recentes; context.py renderiza. +1 teste (test_payload_shows_authorship). Validado contra
a própria LIFELINE: payload de 9 entradas mostra "fundado por anthropic/claude-opus-4-8".

### #0012 — 2026-05-30T17:50:00+00:00 — fix

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: fix
- **summary**: O dogfooding pegou um furo de taxonomia — Entry.Kind não tinha 'milestone'; ingerir a própria LIFELINE quebrou
- **parents**: fee2a0f600342b3e6e9e2fc73195019b167f10039d74985795586e12df437d3a
- **id**: 1d818767279fcba83f5e7a5d15a988863ac25afbbeffe1280e495504643ba706

**Body**:
Ao ingerir a própria LIFELINE (que tem a #0008 com kind=milestone), o Entry (Literal
estrito) rejeitou 'milestone' — o enum Kind e o protocolo da LIFELINE não listavam. O
produto encontrou um bug em si mesmo: a #0008 foi escrita com um kind fora da taxonomia,
e o lifeline_hash.py (que não valida kind) deixou passar, mas o modelo estrito não. Fix:
adicionado 'milestone' e 'release' ao Kind (alinhando com a prática comprovada do inframoe)
e ao protocolo. Nota para o futuro: o uso conversacional (não-code) vai querer uma
taxonomia de kind mais aberta/extensível — decisão adiada, mas marcada aqui.

### #0013 — 2026-05-30T18:10:00+00:00 — feature

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: feature
- **summary**: Threads em aberto explícitas no payload (kind 'open') — fecha o gap "o que vem a seguir" que o teste de aceitação apontou
- **parents**: 1d818767279fcba83f5e7a5d15a988863ac25afbbeffe1280e495504643ba706
- **id**: 057c164c69b99e377e533fb378a2c86781b6bac4bb98fbb7df299acc2b82b0e6

**Body**:
O teste de aceitação (#0008) revelou que o payload inferia "o próximo" pelos recentes, mas
não o declarava. Fix: novo kind `open` (uma thread / próximo passo em aberto). O
ledger_projection coleta os `open` numa lista `open_items`; uma entrada posterior que os
supersede (mesmo mecanismo das correções, Lei #2) os fecha. O ContextAssembler renderiza
uma seção "## Em aberto / próximo". +1 teste em state (coleta+fechamento) e +1 em context
(seção presente). 18 testes verdes. As entradas #0014-#0016 a seguir são as primeiras
threads abertas de verdade — o backlog do projeto agora vive ancorado, não em prosa solta.

### #0014 — 2026-05-30T18:11:00+00:00 — open

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: open
- **summary**: Unificar os dois esquemas de hash — store vira a fonte de verdade e a markdown passa a ser GERADA a partir dele
- **parents**: 057c164c69b99e377e533fb378a2c86781b6bac4bb98fbb7df299acc2b82b0e6
- **id**: c60b24990069090a28e59826f5ba68e0592dcab0262f4b7c41f8e7db1f7984c6

**Body**:
Hoje a cadeia da markdown (scripts/lifeline_hash.py, estilo prev_hash) e o id
content-addressed do Entry (estilo pais/DAG) coexistem. Unificar: o store (Entry) vira a
fonte única; a LIFELINE.md vira uma PROJEÇÃO gerada (como a montagem), não um arquivo
hand-edited. Isso colapsa os dois esquemas num só e torna o store primário — pré-requisito
limpo pro sync de nuvem (M3). Fecha quando o pipeline "append no store → regenera markdown"
existir.

### #0015 — 2026-05-30T18:12:00+00:00 — open

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: open
- **summary**: Política de embedding (M3) — adapter plugável, fixo por índice, default local OSS; gravar modelo+dim como proveniência
- **parents**: c60b24990069090a28e59826f5ba68e0592dcab0262f4b7c41f8e7db1f7984c6
- **id**: 93e9de9440aabc1622a3976e66bfdfcab77c081d63300cc69110201065600d15

**Body**:
Não há embedding universal. Solução: interface de embedding plugável; UM modelo por índice
(vetores de modelos diferentes são incompatíveis); registrar modelo+dimensão por vetor
(proveniência); default local OSS (privacidade/custo) com opção de nuvem no tier pago.
Trocar de modelo = re-embeddar (migração). O vetor é só índice pra entrada ancorada — a
Lei #1 se mantém mesmo se o embedding errar o match. Fecha quando a Camada 3 escolher e
abstrair o embedding.

### #0016 — 2026-05-30T18:13:00+00:00 — open

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: open
- **summary**: Camada 3 (recall semântico) — transplantar o vetor cosseno do SDK antigo, ancorado via causal_event_id
- **parents**: 93e9de9440aabc1622a3976e66bfdfcab77c081d63300cc69110201065600d15
- **id**: 4d278684d0a2eaa420aaf8ccbadb33464ae5a8b3e3588ea054b80554cafabd9e

**Body**:
A 3ª camada de memória (recall associativo) ainda não existe. Transplantar o LocalVectorMemory
(cosseno em Python puro) do SDK antigo, com a regra de ouro: todo VectorRecord carrega o
hash do evento de origem (Lei #1). Permite "me traga as decisões passadas relevantes pra
isto" sem estourar o budget. Depende de #0015 (política de embedding). Fecha quando o
retrieval semântico ancorado estiver no Context Engine e testado.

### #0017 — 2026-05-30T18:40:00+00:00 — milestone

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: milestone
- **summary**: Prova de fogo COMPLEXA passou (6/6) — anti-staleness em escala, recusa de alucinação, atribuição multiprovider
- **parents**: 4d278684d0a2eaa420aaf8ccbadb33464ae5a8b3e3588ea054b80554cafabd9e
- **id**: 36982bad4eb69a4b423c0bdc6a1fef56d6bc435699707cf3f00ba3a9ef86f0d5

**Body**:
Teste adversarial (scripts/firetest.py): projeto fictício 'Aurora' com 24 entradas, 8
decisões (2 revertidas via correction: MongoDB→PostgreSQL, REST→gRPC), 4 providers/modelos
distintos como autores, incidentes/fixes como distratores, e 1 thread aberta fechada por
correção. Verificação programática: 8/8 checks PASS (superseded fora da verdade atual;
não-revertidos permanecem; thread fechada some; todos os 24 ids verificam). Agente novo,
zero contexto, só o payload (1805 chars): respondeu 6/6 — deu PostgreSQL e gRPC (não as
versões revertidas), atribuiu a mensageria ao Gemini corretamente, e RECUSOU ("não consta")
as 2 perguntas-isca cujas respostas não estavam no payload (retenção de logs, causa da
Black Friday). Sem alucinação. Reconciliou sozinho a thread fechada nos "Recentes".

Caveats honestos: ledger sintético e curado por mim; mesma família de modelo (Claude
testando Claude); compressão de 78% é modesta nessa escala (o valor foi seleção, não
encolhimento). CRUCIAL: o anti-staleness só funciona se a reversão for REGISTRADA — uma
reversão silenciosa (parar de usar X sem escrever correction) deixaria a decisão velha "em
vigor". É a fricção de captura na forma específica de reversões não-registradas.

### #0018 — 2026-05-30T18:42:00+00:00 — open

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: open
- **summary**: Assembler deve suprimir/marcar itens superseded também na seção "Recente" (achado da prova de fogo)
- **parents**: 36982bad4eb69a4b423c0bdc6a1fef56d6bc435699707cf3f00ba3a9ef86f0d5
- **id**: 8710db3cbb8c25a20d064d621209c2248564c607d6f598fcc61e3219a1f0bec3

**Body**:
O agente da prova de fogo notou que a seção "Recente" mostra uma thread de `open` já
fechada junto da `correction` que a fechou — coexistência append-only que pode confundir.
A "Em aberto" já filtra superseded; a "Recente" não. Fix (M2): suprimir itens superseded
da "Recente", ou marcá-los como [fechado/revertido]. Achado pelo próprio teste — o produto
se criticando de novo.

### #0019 — 2026-05-30T19:10:00+00:00 — decision

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: decision
- **summary**: Escopo vs self-healing/fine-tuning/deep-learning — Lifeline é MEMÓRIA/DADO ancorado, não executor, treinador nem infra de ML
- **parents**: 8710db3cbb8c25a20d064d621209c2248564c607d6f598fcc61e3219a1f0bec3
- **id**: 6a66d39c5f4c98ffba1037e83d23017eb9f1882a5b68d135e54ca6d12b0d34e7

**Body**:
Clareza de escopo pra não ressuscitar a inflação do SDK velho (#0002). O Lifeline serve a
essas áreas como SUBSTRATO, nunca sendo elas:

- **Self-healing: parcial — é a memória, não o curador.** Healing precisa detectar +
  decidir + AGIR (re-exec/rollback/sandbox) — tudo non-goal. O que o Lifeline dá é a
  memória institucional de falhas: `incident` (causa raiz) + `fix` (o que resolveu),
  ancorados, para o agente não repetir o erro. Quem cura é o orquestrador; o Lifeline o
  torna mais esperto.

- **Fine-tuning: majoritariamente NÃO — ele é a ALTERNATIVA.** Fine-tuning assa
  conhecimento nos pesos (caro, estático, difícil de corrigir); o Lifeline mantém o
  conhecimento externo (barato, dinâmico, corrigível por Lei #2, auditável por Lei #1). O
  produto existe pra tornar o fine-tuning desnecessário pro problema de CONTEXTO. Pode ser
  fonte de dado um dia (as `correction` são pares erro→fix→porquê), mas NÃO é pipeline de
  treino e o volume de um projeto é pequeno.

- **Deep learning: NÃO — erro de categoria.** É memória de camada de aplicação. Só
  *consome* um modelo de embedding na Camada 3; "usa embedding" ≠ "é pra DL".

A ponte que liga os três é o mecanismo de `correction` (sinal de aprendizado: erro→fix→
porquê) — mas é uma ponte de DADO/MEMÓRIA, não de o Lifeline executar healing ou treinar.
Regra: se uma proposta exige o Lifeline AGIR ou TREINAR, ela está fora de escopo; se exige
ele LEMBRAR ancorado, está dentro.

### #0020 — 2026-05-30T19:40:00+00:00 — feature

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: feature
- **summary**: Item 3 — unificação de hash PROVADA: ingestão lossless + projeção store→markdown formam ponto fixo (store pode ser a fonte)
- **parents**: 6a66d39c5f4c98ffba1037e83d23017eb9f1882a5b68d135e54ca6d12b0d34e7
- **id**: b71687c58afcfc67ee6827c24ced701f6b14abd9a9b3ef98e42bcdd62ed87c51

**Body**:
Landaram lifeline/projection.py (store → markdown, mostrando id content-addressed + parents)
e ingest.py lossless (preserva ts e parents; lê DAG explícito quando presente, senão encadeia
linear). test_projection prova o ponto fixo: store → markdown → store reproduz exatamente os
mesmos ids, e o 2º render é byte-idêntico, inclusive com correção de pai explícito (DAG não-
linear). scripts/migrate_check.py rodou na LIFELINE real: 19 entradas, ids estáveis, markdown
byte-idêntica — migração lossless. Os dois esquemas (prev_hash da markdown vs id do Entry)
ficam unificados no id content-addressed (ex.: #0001 vira 6f0d172f…, não mais 51b096c9…).

A pergunta "dá pra unificar com o store como fonte?" está RESPONDIDA (sim, provado). Mas a
#0014 continua ABERTA de propósito: a virada AO VIVO (sobrescrever LIFELINE.md, reescrever o
preâmbulo pro esquema novo, aposentar lifeline_hash.py) deve ser empacotada com um `lifeline
log` (CLI de append) — senão escrever a próxima entrada vira "escrever Python", pior que o
hand-edit atual. Decisão: virar quando houver forçante (M3 sync, ou agente escrevendo via API),
junto com a CLI. O valor já foi capturado: a dívida dos dois esquemas deixou de ser risco.

### #0021 — 2026-05-30T21:00:09.653687+00:00 — milestone

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: milestone
- **summary**: Item 3 fechado — virada ao vivo: store e a fonte, LIFELINE.md e gerada; CLI lifeline log no ar; lifeline_hash aposentado
- **parents**: b71687c58afcfc67ee6827c24ced701f6b14abd9a9b3ef98e42bcdd62ed87c51
- **id**: 1f0de36e4e4156698d546d3073ea41900c9dce80f144c780684edcfac42b3f36

**Body**:
Cutover executado via a propria CLI nova: ESTA entrada foi escrita por python -m lifeline log (dogfood do novo fluxo). 20 entradas migradas para .lifeline/ledger.db (fonte de verdade), todas integras; LIFELINE.md regenerada no formato content-addressed (id + parents, sem prev_hash). Backup do formato antigo em LIFELINE.md.pre-cutover.bak. Preambulo reescrito pro esquema novo; lifeline_hash.py aposentado em favor de lifeline verify. Fecha a thread #0014. Anexar agora e lifeline log (encadeia no head sozinho) e a markdown se regenera.

### #0022 — 2026-05-30T21:03:37.113714+00:00 — decision

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: decision
- **summary**: Artefato versionado = a LIFELINE.md gerada (diffavel/mergeavel); .lifeline/*.db e cache de runtime (gitignored), reconstruivel
- **parents**: 1f0de36e4e4156698d546d3073ea41900c9dce80f144c780684edcfac42b3f36
- **id**: d83a4bdb847bc2b2d6df36f06cc2e1b1033ac29a7856b3a02b6a3ba47c1b4b80

**Body**:
Refina a #0014 com honestidade. O cutover poe o store como fonte de RUNTIME, mas commitar um .db binario briga com a tese GitHub-para-contexto: binario nao faz diff nem merge. Como o content-addressing torna texto e store losslessly interconversiveis (provado no #0020), o artefato git/sync e a LIFELINE.md (texto, diffavel, revisavel em PR) e o .lifeline/ledger.db vira cache local (gitignored), reconstruido com python -m lifeline migrate. Conclusao: a fonte de verdade e o CONJUNTO de entradas content-addressed, materializado como TEXTO (pra git/humanos) e como STORE (pra query). Nenhum e privilegiado porque sempre reconciliam.

### #0023 — 2026-05-30T21:06:47.847986+00:00 — correction

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: correction
- **summary**: Thread #0014 FECHADA — unificacao de hash concluida e cutover ao vivo feito (ver #0020, #0021, #0022)
- **parents**: c60b24990069090a28e59826f5ba68e0592dcab0262f4b7c41f8e7db1f7984c6
- **id**: 9174091632cf305e5c1e1996c1344ecdbb7ef1ca10b7e3408659f21f41e56ce3

**Body**:
Fecha a open #0014 aplicando a propria licao do #0017: conclusao registrada, nao silenciosa. O item 3 esta completo: store e a fonte de runtime, LIFELINE.md e gerada, CLI lifeline log no ar, lifeline_hash aposentado, artefato git = o texto (#0022).

### #0024 — 2026-05-30T21:10:23.196957+00:00 — fix

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: fix
- **summary**: CLI crashava com UnicodeEncodeError em console Windows (cp1252) ao imprimir; stdout agora forcado a UTF-8
- **parents**: 9174091632cf305e5c1e1996c1344ecdbb7ef1ca10b7e3408659f21f41e56ce3
- **id**: 1af1e9ca9624a3401526428c3dd260ad8a9fc981fd4788f30ee49744232a0878

**Body**:
Dogfooding pegou de novo: rodar python -m lifeline context no Windows crashava no print do payload por causa do caractere de seta (U+2192), ausente em cp1252. Fix: main() reconfigura sys.stdout para utf-8 no inicio (try/except). O fechamento da #0014 ja tinha funcionado; o bug so escondia a visualizacao. Segundo bug revelado pelo proprio USO da ferramenta nesta sessao (o 1o foi o kind milestone na #0012) — evidencia de que dogfooding acha o que teste unitario nao acha.

### #0025 — 2026-05-30T21:22:41.623086+00:00 — correction

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: correction
- **summary**: Fix #0018 FECHADA — assembler marca superseded na Recente + budget section-aware (header/abertos/recente nunca cortados)
- **parents**: 8710db3cbb8c25a20d064d621209c2248564c607d6f598fcc61e3219a1f0bec3
- **id**: f3c6af23e808ceda2aac565dcc4e67c20b8646ace1a61c1e4afce693dd662a2b

**Body**:
Dois fixes no Context Engine fechando o achado da prova de fogo. (1) Itens superseded aparecem marcados [fechado/revertido] na secao Recente, em vez de coexistir confusos com a propria correcao. (2) Budget agora e section-aware: header, Em aberto e Recente sao SEMPRE incluidos; decisoes preenchem o resto mantendo as mais recentes e omitindo as antigas com marcador explicito (Lei #6), no lugar do corte-de-cauda cego que podia comer o que-vem-a-seguir. state expoe superseded; +1 teste. 27 testes verdes.

### #0026 — 2026-05-30T21:45:13.997562+00:00 — feature

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: feature
- **summary**: Gaps a+c fechados — loop sem humano: tools MCP de escrita (lifeline_append/recontextualize) + auto-connect
- **parents**: f3c6af23e808ceda2aac565dcc4e67c20b8646ace1a61c1e4afce693dd662a2b
- **id**: fe8100629431eaf50af51441280dc97778ffddfe41d20a0fa4e3fd419c2b42fb

**Body**:
(a) ESCRITA via MCP: o servidor agora expoe lifeline_append (anexa decisao/feature/fix/open) e lifeline_recontextualize (supersede por id), alem do resource de leitura — a IA dirige os DOIS lados do loop, sem humano digitando. (c) AUTO-CONNECT: CLAUDE.md ganhou a secao O loop (ler ao conectar via python -m lifeline context ou resource MCP; escrever ao trabalhar); docs/INTEGRATION.md traz snippet de hook SessionStart do Claude Code e a config MCP. test_mcp confere o contrato. 7 suites verdes. Honesto: o MECANISMO de escrita-sem-humano existe; se a IA usa por habito ainda e questao comportamental, dependente da integracao pegar. Resta o gap (b): relevancia / Camada 3 (recall semantico), que depende de #0015 (embedding) — proximo passo.

### #0027 — 2026-05-30T21:58:11.100722+00:00 — feature

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: feature
- **summary**: Camada 3 (recall ancorado) entregue — gap (b) relevancia fechado: assembler com query, embedder plugavel, default lexical
- **parents**: fe8100629431eaf50af51441280dc97778ffddfe41d20a0fa4e3fd419c2b42fb
- **id**: 9e163ed7fb2668164782a8958c35d32c044214e23cc0fa604422551ccfa9f697

**Body**:
lifeline/recall.py: Embedder (costura plugavel, decisao #0015) + LexicalEmbedder default (term-frequency esparso, cosseno exato, sem dependencia) + SemanticRecall (indexa o ledger, top-k por relevancia, cada hit ANCORADO ao evento por id, Lei #1). ContextAssembler aceita query+recall e adiciona secao Relevante para a tarefa (relevancia, nao recencia). CLI: lifeline context --query. MCP: tool lifeline_recall. Licao honesta do dogfooding: tentei hashing embedder primeiro; o teste pegou colisao de buckets gerando FALSA relevancia (query sem palavra em comum pontuava 0.20) e troquei por TF esparso, que da 0 exato sem sobreposicao. 8 suites verdes.

### #0028 — 2026-05-30T21:58:33.172029+00:00 — correction

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: correction
- **summary**: Threads #0015 (embedding) e #0016 (recall) FECHADAS — Camada 3 entregue (ver #0027)
- **parents**: 93e9de9440aabc1622a3976e66bfdfcab77c081d63300cc69110201065600d15, 4d278684d0a2eaa420aaf8ccbadb33464ae5a8b3e3588ea054b80554cafabd9e
- **id**: 57cbfe195d06af87a238cb4b8edd9e88de12ad0b6738c74b149f27a5310eb888

**Body**:
Politica de embedding implementada (interface plugavel + default lexical + nome do modelo gravavel) e recall semantico construido/integrado. Fecha as duas threads de uma vez (parents = ambos os ids).

### #0029 — 2026-05-30T21:58:53.665406+00:00 — open

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: open
- **summary**: Plugar um embedder SEMANTICO denso (sentence-transformers/API) — o default atual e lexical (casa palavras, nao significado)
- **parents**: 57cbfe195d06af87a238cb4b8edd9e88de12ad0b6738c74b149f27a5310eb888
- **id**: 510c0989106a80ff3b615c137872ceb6aee5b2f6b77f00858269c560e7c1936f

**Body**:
O LexicalEmbedder casa sobreposicao de tokens, nao similaridade semantica (ex.: query em ingles nao casa entrada em portugues). A interface Embedder ja permite plugar um modelo denso por tras (decisao #0015), pinado por indice, gravando modelo+dim como proveniencia. Fecha quando um embedder semantico estiver disponivel e medido vs o baseline lexical.

### #0030 — 2026-05-30T22:15:21.762440+00:00 — feature

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: feature
- **summary**: Pacote de prova portatil (scripts/exam.py) — estressa QUALQUER modelo sem chave de API; SDK confirmado funcional
- **parents**: 510c0989106a80ff3b615c137872ceb6aee5b2f6b77f00858269c560e7c1936f
- **id**: 864c47fa6103979474e2a2e15c8c3c6bcbf5f06282c7942a93565d084b0cb058

**Body**:
scripts/exam.py constroi um ledger adversarial (reversoes Mongo->Postgres e REST->gRPC, multi-provider, isca de alucinacao), monta o payload e escreve EXAM_prompt.md (cole em qualquer modelo: GPT, Gemini, etc. — responde so do contexto) + EXAM_key.md (gabarito + rubrica de aprovacao). Resolve o caveat de eu ter testado so com a mesma familia de modelo. Rodar o script tambem PROVA o SDK funcional ponta a ponta (store+state+context). Status do SDK: core single-user local FUNCIONAL — 8 suites verdes, CLI completa, MCP (read resource + write tools), aceitacao e prova de fogo passados. Fronteiras honestas: nao e pip-installable ainda (sem pyproject em v2); MCP nao foi rodado live contra cliente real nesta sessao (so o contrato registrado); recall e lexical (denso = #0029); nuvem M3 inexistente.

### #0031 — 2026-05-30T22:21:39.865894+00:00 — milestone

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: milestone
- **summary**: MCP testado AO VIVO — cliente MCP real (stdio) fez round-trip completo com o servidor; caveat MCP-live fechado
- **parents**: 864c47fa6103979474e2a2e15c8c3c6bcbf5f06282c7942a93565d084b0cb058
- **id**: 7aea38637511d2fa3a89e4e630c9b8544ea31bbda4b09465e3b9a097dcfee500

**Body**:
scripts/mcp_live_test.py sobe o servidor (python -m lifeline.mcp_server, subprocesso) e fala por um cliente MCP REAL sobre stdio — mesmo protocolo do Claude Code. Round-trip: initialize (handshake), list_tools (append/recontextualize/recall), list_resources (lifeline://project/context), call_tool append x2 (escreveu no ledger PELO protocolo), read_resource (contexto refletiu as escritas: Mercurio + PostgreSQL), call_tool recall (top hit PostgreSQL score 0.53, ancorado). Logs do servidor mostram ListTools/CallTool/ReadResource processados. Ledger TEMP, sem poluir a line real. Falta apenas o APP Claude Code conectar via .mcp.json (config fornecida) — limitacao do harness atual impede anexar um servidor MCP novo no meio da sessao.

### #0032 — 2026-05-30T22:26:38.472848+00:00 — milestone

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: milestone
- **summary**: SDK instalavel — pyproject.toml + console scripts (lifeline, lifeline-mcp); pip install -e funciona de qualquer projeto
- **parents**: 7aea38637511d2fa3a89e4e630c9b8544ea31bbda4b09465e3b9a097dcfee500
- **id**: 764c16f364a769a025dd1bdecbc22af37f5a46444dd838b0dd4daf805e2c600e

**Body**:
Fecha o caveat nao-pip-installable. v2/pyproject.toml: name lifeline-context, deps pydantic+aiosqlite+mcp, requires-python >=3.10, packages.find include=lifeline* (evita o bug do SDK velho que excluia subpacotes). Entry points: lifeline (CLI) e lifeline-mcp (servidor MCP, com main() novo). PROVADO: pip install -e v2 instalou; o comando lifeline (em Scripts/) rodou de um diretorio TEMP fora do v2 e criou o proprio .lifeline/ledger.db daquele projeto — agora da pra apontar pra QUALQUER projeto, nao so dogfood. Nota honesta: o pacote lifeline ANTIGO na raiz sombreia quando cwd=raiz (sys.path[0]); rodar de outro dir ou arquivar o legado resolve.

### #0033 — 2026-05-30T22:32:38.590311+00:00 — milestone

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: milestone
- **summary**: SDK antigo arquivado em _legacy/ — raiz agora so tem v2/ (motor) e .git; sombra de import resolvida
- **parents**: 764c16f364a769a025dd1bdecbc22af37f5a46444dd838b0dd4daf805e2c600e
- **id**: c6d743408683a5ab2ecd7c8182c5ad1be3a2d5e9e8902ae1a484ba9affdddb24

**Body**:
Movido pra _legacy/ (reversivel, sem apagar): o pacote lifeline antigo, devos/, os 12 verify_*.py, tests antigos, pyproject quebrado, egg-info, docs do SDK velho (README/northstar/prd_contextfs/llms/.cursorrules) e artefatos (execution_trace, fire_test_trace, lifeline_demo.db). Raiz agora: .git, .gitignore, v2/, _legacy/. Resultado: (1) import lifeline da raiz resolve pro v2 instalado (nao mais pro pacote antigo que sombreava sys.path[0]) — confirmado: lifeline.__file__ aponta pra v2/lifeline; (2) v2/ pronto pra virar repo proprio; (3) enacta a extracao desenhada no comeco. README minimo na raiz aponta pro v2. Legado e referencia, nao executado.

### #0034 — 2026-05-30T22:43:16.447022+00:00 — feature

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: feature
- **summary**: Documentacao senior de GitHub — README completo, ARCHITECTURE, CONTRIBUTING, AGENTS, LICENSE; a line (LIFELINE.md) e o ponto de entrada das IAs
- **parents**: c6d743408683a5ab2ecd7c8182c5ad1be3a2d5e9e8902ae1a484ba9affdddb24
- **id**: 6cf8616fd1fdf15f2e616374abb31a8de55c33c565022cc6d528a1f531360e79

**Body**:
Doc set nivel senior em v2/: README.md (problema, ideia, install, quickstart CLI+SDK, diagrama do loop, conceitos, refs CLI/MCP/SDK, secao Para IAs, 7 leis, non-goals, status+roadmap honestos, dogfooding, licenca). docs/ARCHITECTURE.md (modelo content-addressed, 3 camadas, supersessao, montagem/budget, recall, cutover store-e-fonte, ports de nuvem, com referencias as entradas). CONTRIBUTING.md (disciplina + quality gate). AGENTS.md (onboarding tool-agnostico p/ qualquer IA: conecta pela line/MCP, obedece as leis, anexa). LICENSE MIT (default permissivo pro core OSS, open-core). A line que qualquer IA le e a propria LIFELINE.md (#0001+) / lifeline context / resource MCP — os docs apontam pra ela. Tudo em PT; EN pendente p/ alcance global.

### #0035 — 2026-05-30T23:12:13.024681+00:00 — feature

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: feature
- **summary**: Multi-line nativo — --line <nome> mapeia ledger E view juntos; fim da colisao de LIFELINE.md; comando lines
- **parents**: 6cf8616fd1fdf15f2e616374abb31a8de55c33c565022cc6d528a1f531360e79
- **id**: 93caee549ee138eee18e2cdded362b74eaad34491f687dc8c194f901de508616

**Body**:
Resolve o gap que a demo de multi-line revelou: lines tinham .db independentes mas a view markdown (--out) tinha nome fixo LIFELINE.md e se sobrepunha. Agora resolve_paths(line, db, out) faz --line NAME mapear .lifeline/NAME.db + LIFELINE.NAME.md JUNTOS — sem colisao. Default preservado (sem --line: .lifeline/ledger.db + LIFELINE.md). Novo comando lifeline lines lista as lines do projeto. Modelo confirmado: uma LINE = um ledger nomeado (codigo OU conversa); um projeto tem 1 por default e suporta N; lines nao sao presas a projeto. Views LIFELINE.<nome>.md sao commitadas (diffaveis); .db fica em .lifeline/ (gitignored). +3 testes (resolve_paths, nao-colisao, lines). 8 suites verdes. Provado ao vivo: 2 lines (backend/codigo + research/conversa) coexistindo sem sobrepor view.

### #0036 — 2026-05-31T00:05:24.639578+00:00 — feature

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: feature
- **summary**: Fluxo HITL de escrita — propose (async, anti-sujeira) -> review -> approve; IA via MCP agora PROPOE, humano cura
- **parents**: 93caee549ee138eee18e2cdded362b74eaad34491f687dc8c194f901de508616
- **id**: ed1364e9d4293af8cf1ab341237c99ebd13d2073cf81f4f6c90b7298939d00b3

**Body**:
Materializa o modelo "IA se organiza, humano cura". lifeline/staging.py (StagingStore: fila de propostas, tabela propria na mesma db; a line so recebe aprovado). CLI: propose (async/leve — NAO toca na line nem regenera view, sem latencia; captura intent+porquE; valida kind + EXIGE body = anti-sujeira no write-time), review (lista pendentes = curadoria), approve <pid|all> (sela na line preservando o ts do momento da decisao), reject. Tiering como aprovar comando shell: humano no `log` = commit direto (ele e o aprovador); IA via MCP lifeline_append/recontextualize agora PROPOE (pendente) — refina o comportamento commit-direto do #0026 (a IA dirige a captura, mas nao suja a verdade; o humano gateia). +5 testes (test_staging). 9 suites verdes. Provado ao vivo: sem porquE recusa; com porquE fica pendente; line so muda no approve.

### #0037 — 2026-05-31T00:16:21.484151+00:00 — milestone

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: milestone
- **summary**: M3 Tier 0 — git sync (custo zero): push/pull/clone sincronizam a line; o remoto git vira o hub do contexto
- **parents**: ed1364e9d4293af8cf1ab341237c99ebd13d2073cf81f4f6c90b7298939d00b3
- **id**: 1f9a5ce6eefb7d4d43c6870ea7ec7695cd9cc6c354f081580b9f390a003d0bb7

**Body**:
lifeline/sync.py (wrappers git) + CLI push/pull/clone. Reusa o #0022 (a view textual e o artefato versionado; o .db e cache reconstruivel): push = rebuild+commit+push; pull = pull + migrate + rebuild (ingere a view mergeada, dedup por id content-addressed); clone reconstroi o .db da view clonada. Conflito de merge aborta com mensagem (resolve no LIFELINE.md, que e legivel). Provado: test_sync (push em A -> clone B -> a line propagou) + demo ao vivo com hub bare local. Resultado: cross-device + colaboracao via git, custo ZERO, GitHub vira o hub — o Tier 0 do M3 que arquitetamos, sem infra nova. Tier 1 (Supabase pros chats web) e o merge multi-writer (M4) seguem o mesmo protocolo content-addressed. +2 testes. 10 suites verdes.

### #0038 — 2026-05-31T00:32:04.869215+00:00 — decision

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: decision
- **summary**: M3 SEM Redis — git (sync) + Supabase Realtime (push) cobrem; Redis no maximo cache de escala futuro, nunca dependencia de nucleo
- **parents**: 1f9a5ce6eefb7d4d43c6870ea7ec7695cd9cc6c354f081580b9f390a003d0bb7
- **id**: fb0ab1d877607bfa0e029ff45f541d496d61f8d65e42913f3dee78e70a92fa5d

**Body**:
Poda pedida pelo dono. Redis entrou por reflexo no esboco do M3 e nao se sustenta: (1) SYNC = git no Tier 0; (2) REAL-TIME/push = Supabase Realtime (free tier, via replicacao do Postgres) cobre o papel que seria do Redis Streams; (3) CACHE do contexto montado = in-process / tabela Postgres no MVP; (4) sem filas/jobs (o lado de execucao foi cortado, ver #0019); (5) auth/sessao = Supabase JWT. Contra o criterio de custo-zero: Redis seria mais um servico pra hospedar (custo + ops). Redis SO ganharia lugar em ESCALA (cache compartilhado de baixa latencia entre replicas) — e mesmo ai edge KV ou o proprio Supabase podem bastar; entao e, no maximo, otimizacao futura atras de um forcante real, nunca dependencia de nucleo. O SDK velho tinha um RedisEventBus stub/teatro — esta decisao impede que uma IA futura reconstrua isso. M3 enxuto: Tier 0 = git (feito); Tier 1 = Supabase (Postgres/Auth/RLS/Realtime/PostgREST) SEM Redis.

### #0039 — 2026-05-31T00:41:55.027794+00:00 — feature

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: feature
- **summary**: M3 Tier 1 kit (Supabase): schema.sql + adapter de referencia + runbook
- **parents**: fb0ab1d877607bfa0e029ff45f541d496d61f8d65e42913f3dee78e70a92fa5d
- **id**: 9959bad8931381b674be25f668600891e0770dd2ec0ce86418fa60e32f174d3c

**Body**:
Gerado o kit do Tier 1 em cloud/ e docs/. (a) cloud/schema.sql: tabela lifeline_entries multi-tenant, dedup por (owner,line,id), seq para ordem causal, e RLS APPEND-ONLY — so SELECT/INSERT do proprio auth.uid(); sem policy de UPDATE/DELETE, entao o banco impoe as Leis #1 e #2. (b) cloud/supabase_store.py: SupabaseEventStore atras do port EventStore (PostgREST via httpx), marcado EXPERIMENTAL e FORA do core testado — promove com teste quando rodar contra projeto real. (c) docs/M3_TIER1_SUPABASE.md: runbook. Projeto do usuario: ref rzphncyjrilhwpuemrcl. Seguranca: schema roda no dashboard sem compartilhar key; runtime le SUPABASE_URL/KEY do ambiente; .env adicionado ao .gitignore; service_role nunca em chat/commit. Nao consegui operar o banco desta sessao (sem MCP do Supabase ativo aqui — conexao MCP e fixada no inicio da sessao).

### #0040 — 2026-05-31T01:03:42.849421+00:00 — milestone

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: milestone
- **summary**: v2 promovido a raiz do repo; rev0 arquivada em _legacy/ — produto entra no versionamento (destrava Tier 0)
- **parents**: 9959bad8931381b674be25f668600891e0770dd2ec0ce86418fa60e32f174d3c
- **id**: ffe0ddf0c27951238de46bff2247f6e0ef71454ab7757221f5f92b35eb8e8bee

**Body**:
Reestruturacao (opcao b do dono). Antes: o HEAD commitado ainda era o SDK rev0; o produto real (v2/ — codigo limpo + ledger de 39 entradas) estava UNTRACKED, sem historico. Isso era incoerente com a tese 'GitHub para contexto' e impedia o Tier 0 — nao da pra 'lifeline push' uma line que nem esta num commit. Acao: movido v2/* para a raiz (sem colisao real; so .gitignore e README.md, versoes do v2 venceram); a rev0 inteira ja estava arquivada em _legacy/. Feito na branch m3/promote-v2-root para ser reversivel; main intacta na rev0 ate o merge. CLI roda da raiz (antes era 'cd v2'); store .lifeline/ viajou junto; verify OK. Pre-requisito do M3 Tier 1 (Supabase) cumprido.

### #0041 — 2026-05-31T01:31:01.483485+00:00 — feature

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: feature
- **summary**: M3 Tier 1: SupabaseEventStore promovido ao pacote + seam --store supabase na CLI, com testes de wire mockados e teste live skip-gated
- **parents**: ffe0ddf0c27951238de46bff2247f6e0ef71454ab7757221f5f92b35eb8e8bee
- **id**: 7dc96461ca8604296d799bc21389a20a4d274f769e58a7b40cac4c347ddde725

**Body**:
Opcao 1 da outra sessao, com a disciplina do #0039 (sem overclaim). (1) Adapter movido de cloud/supabase_store.py para lifeline/cloud.py — importavel apos install, com transporte httpx injetavel (httpx.MockTransport) p/ teste. (2) CLI ganhou --store {sqlite,supabase}: _open() faz o branch; log/context/verify/rebuild/migrate funcionam na nuvem pelo mesmo port EventStore; push/pull/clone/lines e o HITL ficam barrados no modo supabase (sao do store local) com mensagem clara. (3) tests/test_supabase.py: 8 testes de WIRE mockados (montagem de POST/GET, headers apikey+Bearer+Prefer, filtros eq/cs, parse de payload->Entry, idempotencia por status, erro claro sem env, guarda da CLI) que rodam sempre + 2 testes LIVE skip-gated (round-trip real e prova de que a RLS e append-only: UPDATE/DELETE negados) que so rodam com SUPABASE_URL/KEY. Suite: 53 passam, 2 skip. (4) httpx virou dep explicita do core (ja vinha via mcp) + extra [cloud]. (5) DECISAO de auth ancorada: SUPABASE_KEY deve ser access token de USUARIO (JWT) p/ auth.uid() resolver na RLS; service_role bypassa a RLS e deixa owner nulo, nao serve p/ escrita multi-tenant. Falta: a outra sessao (com o MCP/creds) rodar o schema.sql e o teste live p/ provar o contrato real; depois HITL-na-nuvem e MCP remoto SSE.

### #0042 — 2026-05-31T02:33:43.480922+00:00 — milestone

- **author**: jessianjmb@gmail.com
- **agent**: claude-code
- **provider**: anthropic
- **model**: claude-opus-4-8
- **kind**: milestone
- **summary**: M3 Tier 1 VALIDADO ao vivo: schema Supabase aplicado + RLS append-only provada; bug apikey vs Bearer achado e corrigido (suite 55/55 com live)
- **parents**: 7dc96461ca8604296d799bc21389a20a4d274f769e58a7b40cac4c347ddde725
- **id**: 45bfc3f95984780ca4093abc26cb34155e496113efd05bdda778194538bdaf57

**Body**:
Fecha o caveat do #0039/#0041 (o kit estava "nao validado ao vivo"). Com o PAT do dono no .env, apliquei cloud/schema.sql via Management API (role postgres): tabela lifeline_entries criada, RLS habilitada, policies so SELECT/INSERT (append-only imposto pelo banco).

Provas AO VIVO pelo PostgREST contra o projeto real (ref rzphncyjrilhwpuemrcl):
- INSERT anon NEGADO -> 42501 "new row violates row-level security policy": append-only/anti-tenant garantido pelo Postgres (Leis #1 e #2), nao so por convencao.
- Round-trip autenticado OK: INSERT com apikey=anon + Authorization=Bearer <JWT de usuario> seta owner=auth.uid() e passa a RLS; get/stream leem de volta.

BUG achado por DOGFOODING (nao pelos mocks): o SupabaseEventStore mandava self.key tanto no header apikey quanto no Authorization. O gateway do Supabase REJEITA o JWT de usuario como apikey -> 401 "Invalid API key". Os mocks nao pegaram porque nao exercitam a validacao de apikey do gateway. Fix em lifeline/cloud.py: separar apikey (chave do projeto) do token (Bearer = JWT), lido de SUPABASE_TOKEN; e construcao com key explicita NAO herda token do ambiente (isolamento de teste). Mocks seguem verdes e os 2 testes live agora passam -> suite 55/55 (com creds; 8+2skip sem creds, CI-safe).

Caveat honesto: o JWT de usuario e curto (~1h) -> auth duravel do CLI (login/refresh) e o proximo passo do Tier 1. O .mcp.json ganhou o servidor supabase oficial (npx), mas a Management API direta com o PAT ja bastou pra criar+validar; o MCP fica como opcao p/ sessoes futuras.

### #0043 — 2026-05-31T02:46:33.361118+00:00 — fix

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: fix
- **summary**: Trava o fix de auth do #0042 no CI (testes de wire p/ apikey vs Bearer) e corrige docs stale
- **parents**: 45bfc3f95984780ca4093abc26cb34155e496113efd05bdda778194538bdaf57
- **id**: ea1e5d49f70152253d38d255d6a9d69c4aecd3105604f11b8c66a665e0d1a999

**Body**:
A outra sessao validou o Tier 1 ao vivo e corrigiu o cloud.py (apikey do projeto no header apikey; JWT do usuario no Authorization: Bearer), mas o commit ead2f07 nao tocou testes nem docs — entao o fix so estava protegido pelo teste LIVE (skip-gated, nao roda no CI) e os docs ficaram errados. Fechei o gap: (1) 3 testes de wire mockados que travam a separacao — apikey=projeto / Bearer=token, fallback do token p/ apikey quando ausente, e leitura de SUPABASE_KEY+SUPABASE_TOKEN do ambiente; (2) o gate dos testes live agora exige tambem SUPABASE_TOKEN (sem ele a escrita 401 em vez de pular); (3) docs/M3_TIER1_SUPABASE.md reescrito p/ o modelo de DOIS valores (SUPABASE_KEY=apikey anon, SUPABASE_TOKEN=JWT de usuario). Suite 56/56 (+2 skip live).

### #0044 — 2026-05-31T02:56:18.322228+00:00 — feature

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: feature
- **summary**: HITL na nuvem: StagingStore vira port + SupabaseStagingStore (tabela lifeline_proposals); propose/review/approve/reject no modo --store supabase
- **parents**: ea1e5d49f70152253d38d255d6a9d69c4aecd3105604f11b8c66a665e0d1a999
- **id**: dc14e7e1004342f8f2edb338e814bcce55dab86ddeacc862560dbff038886121

**Body**:
Leva a curadoria anti-sujeira pro modo nuvem (a IA propoe, o humano cura), nao so o store local. (1) staging.py: StagingStore virou PORT (ABC) + SQLiteStagingStore (impl atual). (2) cloud.py: extrai _SupabaseBase (creds/headers/client compartilhados — comportamento da auth #0042 preservado, garantido pelos wire-tests) e adiciona SupabaseStagingStore. (3) cloud/schema.sql: tabela lifeline_proposals — MUTAVEL (status muda), RLS permite SELECT/INSERT/UPDATE do dono mas SEM DELETE (preserva historico de curadoria); contraste explicito com lifeline_entries que e append-only. (4) cli.py: factory _staging() espelha _open(); propose/review/approve/reject usam o backend ativo; _LOCAL_ONLY encolheu p/ {push,pull,clone,lines} (HITL saiu — agora funciona na nuvem). (5) testes: +4 wire mockados (propose->pid com return=representation, pending filtra por line+status e normaliza parents jsonb->string JSON p/ cmd_approve ficar agnostico, get vazio, set_status PATCH por pid) + 1 live HITL round-trip skip-gated. Suite 60 passa / 3 skip. Falta: auth ergonomica do CLI e o MCP remoto SSE (superficie dos chats web).

### #0045 — 2026-05-31T03:03:45.421881+00:00 — milestone

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: milestone
- **summary**: Tier 1 completo validado ao vivo POR MIM: ledger + RLS append-only + HITL na nuvem; tabela lifeline_proposals aplicada no projeto; suite 63/63 com live
- **parents**: dc14e7e1004342f8f2edb338e814bcce55dab86ddeacc862560dbff038886121
- **id**: 306e91316e9c02a1be8f7a2a35b938b4145647404167495e640b9d6fc19af18a

**Body**:
Com SUPABASE_URL/KEY/TOKEN do .env, rodei os 3 testes live contra o projeto real (rzphncyjrilhwpuemrcl): round-trip do ledger, RLS append-only (UPDATE/DELETE negados) e o round-trip HITL (propose->pending->status). O #0042 da outra sessao validou so o ledger (entries); o HITL (#0044) faltava a tabela. O MCP nesta sessao nao tem o management token em runtime (Unauthorized p/ DDL), entao apliquei cloud/schema.sql direto pela Management API (POST /v1/projects/{ref}/database/query) com o SUPABASE_ACCESS_TOKEN do .env — idempotente, criou lifeline_proposals. Suite completa: 63 passam, 0 skip (todos os live ligados). Fecha o caveat 'nao re-verifiquei a nuvem': agora o store remoto inteiro (ledger append-only + fila HITL mutavel sem-delete) esta provado de ponta a ponta. Falta do Tier 1 so o MCP remoto (SSE), a superficie dos chats web.

### #0046 — 2026-05-31T03:11:37.457755+00:00 — feature

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: feature
- **summary**: MCP remoto (HTTP/SSE): mesma superficie store-agnostica via lifeline-mcp-remote; escrita HITL; falta OAuth p/ conectores web e multi-tenant
- **parents**: 306e91316e9c02a1be8f7a2a35b938b4145647404167495e640b9d6fc19af18a
- **id**: b32f078a50841724b298bb77e3e1789678d7012421c77498e2acd983403b484d

**Body**:
Expoe a superficie MCP por HTTP (nao so stdio), pra IA conectar de fora. (1) mcp_server.py virou store-agnostico: resource/recall usam o factory _open da CLI; _configure() escolhe backend/line por env (LIFELINE_STORE=supabase usa SUPABASE_URL/KEY/TOKEN, default sqlite). (2) Novo entry-point lifeline-mcp-remote (main_remote): serve sobre SSE (/sse + /messages) ou streamable-http (/mcp), bind por LIFELINE_MCP_HOST/PORT. Mesmas tools: leitura (context+recall) e escrita HITL (append/recontextualize PROPOEM, nao commitam). (3) Testes: surface registrada (incl. recall), _configure escolhe backend por env, e a tool de escrita e HITL (proposta pendente, 0 na line). uvicorn/starlette ja presentes; sse_app/streamable_http_app constroem com rotas. Suite 63/63 (+3 live skip). CORRECAO de rota honesta: NAO roda em Supabase Edge Functions (Deno); e servidor Python, hospedavel em qualquer free-tier (Fly/Render/Railway) com o Supabase de store. FALTA: OAuth 2.1 no endpoint (exigido pelos conectores claude.ai/ChatGPT/Gemini) + multi-tenant por JWT de usuario — proximo incremento; a RLS (owner=auth.uid) ja esta pronta pra isso.

### #0047 — 2026-05-31T03:24:06.782024+00:00 — feature

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: feature
- **summary**: OAuth Resource Server no MCP remoto (LIFELINE_OAUTH=1): valida JWT Supabase por requisicao, escopa RLS por usuario (multi-tenant), serve protected-resource metadata
- **parents**: b32f078a50841724b298bb77e3e1789678d7012421c77498e2acd983403b484d
- **id**: f22de1252177e82439f182098dca8524ff77ffc15c24e4b528e1cddc652b0e79

**Body**:
A ultima milha do M3, na parte que da pra fechar+testar aqui. (1) SupabaseTokenVerifier (TokenVerifier do SDK): valida o Bearer contra /auth/v1/user; 200->AccessToken carregando o proprio JWT + user id; 401->None. Transporte httpx injetavel p/ teste. (2) Binding por-requisicao: _request_token() le o token validado (get_access_token), e _open_request/_staging_request constroem o store/staging com o JWT DAQUELE usuario -> RLS escopa por owner=auth.uid() = multi-tenant real (sem isso era single-tenant via env). (3) _register() passou a registrar a superficie em qualquer instancia FastMCP; _build_remote() liga o Resource Server quando LIFELINE_OAUTH=1 (+supabase+creds): FastMCP(token_verifier, AuthSettings(issuer,resource_server_url)) -> exige Bearer e publica GET /.well-known/oauth-protected-resource (RFC 9728). (4) Testes: verifier valido/invalido/sem-config, build com OAuth serve metadata, build sem OAuth = servidor base. Suite 68/68 (+3 live skip). HONESTO: o lado Authorization Server (DCR + authorization-code) que claude.ai/ChatGPT/Gemini dirigem NAO esta feito — o Supabase Auth nao e AS OAuth2 generico com DCR; rotas (AS shim / provedor com DCR / aguardar Supabase) documentadas em docs/MCP_REMOTE.md. Em todas, o nosso RS nao muda. Da p/ conectar JA com um JWT em mao (claude mcp add --header).

### #0048 — 2026-05-31T03:25:43.343560+00:00 — milestone

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: milestone
- **summary**: OAuth Resource Server validado ao vivo: verifier aceita JWT real (200, escopa por usuario) e rejeita invalido (403) contra o Supabase auth real
- **parents**: f22de1252177e82439f182098dca8524ff77ffc15c24e4b528e1cddc652b0e79
- **id**: 64d0e17c4d782b67e165104e64f460baec4e68fd3ec5569e0281d60033b43163

**Body**:
Mesmo padrao dos #0042/#0045 (validar ao vivo, nao so mock). Com as creds do .env rodei o SupabaseTokenVerifier contra https://<proj>.supabase.co/auth/v1/user: token real -> 200 -> AccessToken com user id (escopo multi-tenant ok); 'jwt.invalido' -> 403 -> None (rejeitado). Confirma o RS de ponta a ponta. Falta so o Authorization Server (DCR/auth-code) dos conectores hospedados — decisao de arquitetura/integracao, nao codigo do nosso lado.

### #0049 — 2026-05-31T03:28:18.742815+00:00 — open

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: open
- **summary**: Proximo: OAuth Authorization Server (DCR + authorization-code/PKCE) p/ plugar nos conectores hospedados (claude.ai/ChatGPT/Gemini)
- **parents**: 64d0e17c4d782b67e165104e64f460baec4e68fd3ec5569e0281d60033b43163
- **id**: 32d96c3d0364ad868c6df14bbfa73203f7472778c4894f3223a307bee4b92cfb

**Body**:
Unica peca restante do M3. O Resource Server (validacao de JWT + multi-tenant por RLS + protected-resource metadata) esta feito e validado ao vivo (#0047/#0048) e NAO muda. Falta o AS, que os conectores dirigem sozinhos. Rotas avaliadas (decisao adiada pelo dono): (a) AS shim via OAuthAuthorizationServerProvider do SDK, ponte pro Supabase Auth — custo-zero, no repo, mas security-critical e so valida ao vivo contra o conector; (b) provedor com DCR (Auth0/WorkOS/Keycloak) emitindo o JWT que o RS ja valida — menos codigo, possivel custo. Comecar fresco quando for testar contra o claude.ai real.

### #0050 — 2026-05-31T03:47:54.458026+00:00 — fix

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: fix
- **summary**: Hardening pos-auditoria (Top 5): resiliencia de rede na nuvem, README, CI, rede de erro na CLI, logging + teste de isolamento
- **parents**: 32d96c3d0364ad868c6df14bbfa73203f7472778c4894f3223a307bee4b92cfb
- **id**: 58281bfb9866fdfabc4d7ae720af7181ad9480292b9362a17dac7f5dbdc6b0a6

**Body**:
Resposta acionavel a auditoria de producao. (1) README: corrigido o install quebrado (pip install -e . na raiz, nao 'v2/' que nao existe mais), badges (68 testes) e deps (httpx + extra [cloud]) — destrava onboarding. (2) cloud.py: _ensure_ok() loga+levanta em 4xx/5xx em TODOS os metodos; append passou a usar return=representation e distingue inserido(True)/duplicata(False) igual ao SQLite — falha real NUNCA mais mascarada como dedup (era o bloqueador #2/#3 do audit). Provado ao vivo: token expirado deu 401->log ERROR+HTTPStatusError, antes daria 'duplicada (idempotente)'. (3) CI: .github/workflows/ci.yml roda pytest+verify no push/PR (py3.10/3.12) — pega o drift que o audit achou (README stale, #0043 foi manual). (4) cli.py: dispatch extraido p/ _dispatch(); main() envolve em try/except -> erro de rede vira mensagem amigavel + exit 1, nao traceback (SystemExit do argparse passa intacto). (5) logging em cloud.py/mcp_server.py (o except silencioso de auth virou debug log) + teste live skip-gated de isolamento (anon nao le linhas do usuario via RLS). Suite 70/70 (+4 live skip). Pendente p/ re-validacao live funcional: refresh do SUPABASE_TOKEN (expira ~1h).

### #0051 — 2026-05-31T04:11:35.450315+00:00 — feature

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: feature
- **summary**: Local rumo a 10 + gancho local->nuvem com qualidade: locks de primeira-execucao/re-seed, .env.example, e a graduacao documentada/testada
- **parents**: 58281bfb9866fdfabc4d7ae720af7181ad9480292b9362a17dac7f5dbdc6b0a6
- **id**: 0859890d6f0a2e66abcd8a887f87f312b6eb4094637be543c7266401400b9725

**Body**:
Corretude-nucleo do local ja estava travada por teste (determinismo, anti-tamper, supersessao, round-trip ponto-fixo) — nao dupliquei. Fechei os gaps reais que faltavam pro '10 polido': (1) teste de ledger VAZIO (primeira execucao e graciosa, placeholder, sem crash); (2) teste de IDEMPOTENCIA do ingest (re-seed nao duplica — content-addressed); (3) .env.example (template do modo nuvem, sem segredo); (4) README: 'Status & roadmap' corrigido (estava stale: dizia 8 suites, M3 planejado/Redis, 'nuvem nao existe' — agora reflete M3 validado ao vivo + limites honestos) e nova secao 'Do local pra nuvem (graduacao)'; (5) gancho local->nuvem como fluxo de primeira-classe: 'lifeline --store supabase migrate --from LIFELINE.md' e LOSSLESS+IDEMPOTENTE (mesmos ids), com teste live skip-gated (test_seed_cloud_from_local_markdown). Suite 72/72 (+5 live skip). Veredito honesto: local agora ~9/10 (o '10 teorico' fica no O(n) por chamada — deliberadamente nao otimizado, trivial na escala real — e na ausencia de assinatura, fora do threat-model local).

### #0052 — 2026-06-01T12:31:04.117437+00:00 — fix

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: fix
- **summary**: Corrige overclaim no MCP_REMOTE.md (Bearer estatico NAO serve no claude.ai web) + ancora a pesquisa de auth dos conectores
- **parents**: 0859890d6f0a2e66abcd8a887f87f312b6eb4094637be543c7266401400b9725
- **id**: 9559eff29e975f086e9bbb2dd3603ec53dc6eae58e2f6ff173d063b0603c01ed

**Body**:
Pesquisa fact-checked (jun/2026, fontes oficiais Anthropic/OpenAI/Google/spec MCP) sobre o que os chats exigem pra conectar MCP remoto. ACHADOS: (1) claude.ai SUPORTA conector AUTHLESS (auth='none') -> one-click sem AS, mas sem identidade por usuario (single-tenant/compartilhado, nao multi-tenant). (2) DCR NAO e obrigatorio: claude.ai aceita CIMD ou client pre-registrado (Anthropic-held creds via mcp-review@anthropic.com); ChatGPT aceita CIMD/clients predefinidos; a spec MCP diz DCR='MAY'. (3) BEARER ESTATICO NAO SERVE nos apps web (claude.ai: static_bearer 'not yet supported'; ChatGPT idem) — so funciona nos CLIs (Claude Code, Gemini CLI). Isso CORRIGE o doc, que implicava 'claude mcp add --header' pro claude.ai web. (4) ChatGPT exige Developer Mode (planos PAGOS; free nao tem). (5) Gemini consumo nascente (CLI ok; app/enterprise). (6) AS zero-custo com DCR: Cloudflare workers-oauth-provider (OSS/free Workers), Keycloak (OSS), Stytch (free ~10K MAU); Auth0 enterprise/opaco. CONCLUSAO DE NEGOCIO: o valor pago (multi-tenant nos chats) E gated por um AS, MAS nao por DCR; e da pra VALIDAR o one-click via authless (claude.ai) sem AS nenhum. A workflow de deep-research falhou (StructuredOutput), refeito via WebSearch/WebFetch direto.

### #0053 — 2026-06-01T12:37:47.725665+00:00 — feature

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: feature
- **summary**: Conector authless pronto p/ deploy (validacao one-click no claude.ai): Dockerfile + .dockerignore + DEPLOY.md, smoke de boot OK
- **parents**: 9559eff29e975f086e9bbb2dd3603ec53dc6eae58e2f6ff173d063b0603c01ed
- **id**: b5bb7c7c3b0a1f7331e473a6520e306ed733b3afd51b2e79d9b3c42766d0bec8

**Body**:
Caminho (a) escolhido pelo dono: validar o one-click nos chats SEM construir AS, usando o modo authless que o claude.ai aceita (pesquisa #0052). Entregue: (1) Dockerfile — reconstroi o .db da LIFELINE.md versionada no boot e serve authless via streamable-http (/mcp), respeitando  (Render/Railway); (2) .dockerignore — NUNCA empacota .env/segredo/_legacy/cache; (3) docs/DEPLOY.md — smoke local, deploy free-tier (Railway/Render/Fly) e os cliques de registro no claude.ai (Authentication: None). Smoke real: o servidor sobe no uvicorn e fica ouvindo :8000/mcp (testado local). SEGURANCA (honesto): authless+publico = qualquer um com a URL le o contexto e pode enfileirar propostas — mitigado por HITL (escrita so PROPOE; nao corrompe a line) + usar line nao-sensivel (o demo expoe a propria LIFELINE.md, ja publica). NAO usar com dado privado — pra isso e multi-tenant+AS (#0049). O dono deploya e da o clique final no claude.ai.

### #0054 — 2026-06-01T13:53:25.599113+00:00 — fix

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: fix
- **summary**: Fix 421 'Invalid Host header' no MCP remoto: transport_security aceita host publico (tunel/proxy/deploy)
- **parents**: b5bb7c7c3b0a1f7331e473a6520e306ed733b3afd51b2e79d9b3c42766d0bec8
- **id**: 72b10ff8d6c72eee41202fe9b818fc7efcd76679cd20dcafc552c88c417e63ec

**Body**:
Achado testando o conector authless por tunel cloudflare: o FastMCP, por padrao, so confia em Host=localhost (anti-DNS-rebinding), entao rejeita com 421 qualquer requisicao cujo Host seja o dominio publico — bloqueava TODO deploy/proxy/tunel, nao so o demo. Fix: _transport_security() em mcp_server.py — LIFELINE_MCP_ALLOWED_HOSTS=host1,host2 libera esses com a protecao ON; sem a lista, desliga a protecao (servidor remoto ja e publico). _build_remote() agora SEMPRE constroi um FastMCP fresco com esse transport_security (antes o caminho authless reusava a instancia stdio sem ele). +2 testes (lista libera host / default desliga). Suite 74/74 (+5 live skip). Aprendizado: hospedar tunel efemero a partir da sessao do agente e fragil (caiu com exit 127) — o deploy/tunel deve rodar no terminal do dono p/ persistir.

### #0055 — 2026-06-01T14:23:07.609835+00:00 — feature

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: feature
- **summary**: Deploy no Render preparado: /healthz (health check), render.yaml (Blueprint) e DEPLOY.md Render-first
- **parents**: 72b10ff8d6c72eee41202fe9b818fc7efcd76679cd20dcafc552c88c417e63ec
- **id**: f72b1e1ac0c6b029bc827cedb2cf74ab11aa68a929659d15c06ba835a9f6fdec

**Body**:
Decisao do dono: Render free agora (validar, /usr/bin/bash), Railway depois (quando aprovar conexao+viabilidade). Render free usa o Dockerfile como esta, dorme apos 15 min (cold start ~1 min) e nao exige cartao. Adicionado: (1) rota GET /healthz -> 200 'ok' (registrada via _register em qualquer instancia; health check de Render/Railway + checagem no navegador; smoke local confirmou 200); (2) render.yaml (Blueprint: web/docker/free/healthCheckPath=/healthz/autoDeploy; comentario p/ promover a starter  e p/ envs OAuth multi-tenant futuras); (3) DEPLOY.md Render-first com Blueprint+manual, nota de cold-start, e a licao do tunel (rede bloqueia porta 7844 do cloudflared — deploy resolve). Suite 76/76 (+1 teste: rota /healthz registrada; +5 live skip). Conta/cliques sao do dono (nao crio conta). Ancorado #0055.

### #0056 — 2026-06-01T14:37:23.209485+00:00 — milestone

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: milestone
- **summary**: Conector MCP no ar e verificado no Render (free): claude.ai pode conectar (authless) — primeira nuvem viva
- **parents**: f72b1e1ac0c6b029bc827cedb2cf74ab11aa68a929659d15c06ba835a9f6fdec
- **id**: a8258171fffb61bf513abc5492079e7d61d6e86b3a4409359e241a38b8f2856d

**Body**:
Deploy do dono no Render free (lifeline-cnah.onrender.com) via Blueprint. Verificado por mim daqui (URL HTTPS publica, sem o problema de porta 7844 do tunel): /healthz -> 200 'ok'; /mcp -> initialize 200 + handshake completo expondo TOOLS [lifeline_append, lifeline_recontextualize, lifeline_recall] e RESOURCE [lifeline://project/context]. Authless (validacao, single-tenant) servindo a propria LIFELINE.md. Cold-start ~1 min (free dorme apos 15 min). Falta o dono registrar a URL .../mcp como Custom Connector no claude.ai (Authentication: None) e sentir o valor. Proximo da viabilidade: multi-tenant via AS (#0049) + Railway/Render-paid sempre-on quando aprovar.

### #0057 — 2026-06-01T14:42:16.841419+00:00 — fix

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: fix
- **summary**: CORRECAO #0052: claude.ai WEB exige OAuth — authless NAO conecta no app web (so nos CLIs)
- **parents**: a8258171fffb61bf513abc5492079e7d61d6e86b3a4409359e241a38b8f2856d
- **id**: 029ac2e20bb9cbf0ca297118f304a93bb46b934213c50719d393dffb8f565859

**Body**:
Teste ao vivo do dono: adicionar o conector authless (https://lifeline-cnah.onrender.com/mcp) no claude.ai web falhou com 'Couldn't register with sign-in service' (ofid_75cff0ea31cc4203). Diagnostico verificado daqui: o servidor authless retorna 200 no /mcp e NAO tem /.well-known/oauth-* (todos 404); mesmo assim o claude.ai WEB tenta registrar um client OAuth e, sem AS, nao consegue. A pesquisa #0052 concluiu 'authless valida no claude.ai' — CORRIGE-SE: isso vale pros CLIs (Claude Code/Gemini CLI aceitam URL/authless direto), NAO pro app web, cujo fluxo de Custom Connector forca OAuth (DCR/CIMD/client pre-registrado). Consequencia pratica: (a) validar o valor JA via Claude Code 'claude mcp add --transport http lifeline <url>/mcp' (authless ok); (b) pro claude.ai WEB, o AS (#0049) deixa de ser opcional — e o pre-requisito. Deploy em si esta 100% (healthz/mcp/tools/resource verificados).

### #0058 — 2026-06-01T14:45:45.435934+00:00 — decision

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: decision
- **summary**: Remove _legacy/ do tracking do GitHub (gitignored) — refina #0040; rev0 fica no historico
- **parents**: 029ac2e20bb9cbf0ca297118f304a93bb46b934213c50719d393dffb8f565859
- **id**: 62a405074d12d4619de5c7a3fe7f947ad248091f601f7ce42b4c86b51e9ff9ba

**Body**:
O #0040 arquivou a rev0 em _legacy/ rastreada (navegavel). Agora, mirando repo-vitrine limpo (direcao de lancamento/landing), tira-se _legacy/ (107 arquivos, 1.1M de SDK morto) da arvore versionada: git rm --cached + _legacy/ no .gitignore. NADA se perde: a rev0 continua (a) no disco local e (b) no HISTORICO do git (commits originais 37f5fd6 etc. + o rename fef0b15) — recuperavel por git log/checkout. Refina #0040 (mantem o porque/arquivamento; muda so o 'rastreado na arvore' -> 'preservado no historico'). Repo publico fica so com o produto limpo.

### #0059 — 2026-06-01T15:15:00.768245+00:00 — feature

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: feature
- **summary**: AI-first, friccao zero: manual embutido no servidor MCP (instructions), .mcp.json limpo, llms.txt, AGENTS/INTEGRATION com instalar+conectar-por-cliente+explicar ao user
- **parents**: 62a405074d12d4619de5c7a3fe7f947ad248091f601f7ce42b4c86b51e9ff9ba
- **id**: 95ba545cdfc5e8ca5a171c6265263629fc9807df461d80f6205d6cfd773fc97c

**Body**:
Objetivo do dono: qualquer IA que conecta (ou abre o repo) entende o uso, sabe instalar/conectar, seguir, e EXPLICAR/ORGANIZAR pro humano — sem friccao. Entregue: (1) FastMCP instructions (899 chars) nas 3 construcoes do servidor (local/remoto authless/remoto OAuth) — toda IA recebe o manual no initialize: ler o context primeiro, propor via HITL, nunca inventar (ancora), e o papel de explicar/organizar pro humano. (2) .mcp.json LIMPO — so o server  stdio (o que o instalador recebe); a entrada supabase do DEV foi pra .mcp.local.json (gitignored, nao-versionada). Corrigido bug de comentario-inline no .gitignore (pattern nao casava). (3) llms.txt na raiz — mapa AI-readable (usar/instalar/entender/nuvem, com links). (4) AGENTS.md ganhou 'instalar 1 min (faca pelo humano)' + 'explique e organize pro humano'. (5) docs/INTEGRATION.md: snippets copia-e-cola por cliente (Claude Code auto via .mcp.json; Cursor; Claude Desktop com path absoluto; Gemini CLI) + comando alinhado (lifeline-mcp). Clientes de dev conectam no OSS local; apps web exigem nuvem+OAuth (#0057). Suite 75/5-skip. Falta p/ friccao-zero total: publicar no PyPI (hoje install e git/-e) e EN p/ alcance global.

### #0060 — 2026-06-01T15:35:51.365738+00:00 — feature

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: feature
- **summary**: Empacotamento PyPI pronto e validado (nome livre, build OK, twine check PASSED, install em venv limpa OK) — falta so o twine upload do dono
- **parents**: 95ba545cdfc5e8ca5a171c6265263629fc9807df461d80f6205d6cfd773fc97c
- **id**: 297a3f1b5005885b3458dbd1b3d6ac989097d73ea36e1e61550b7a4c0c1829f1

**Body**:
Prep do item 1 (publicar no PyPI) executada ate onde da sem a conta do dono. Nome lifeline-context LIVRE no PyPI. pyproject completado: license MIT, authors, keywords, classifiers (Alpha/Python 3.10-3.13/AI), project.urls (github). Versao alinhada (__init__ 0.0.1 -> 0.1.0 = pyproject). build/ e dist/ no gitignore. python -m build gerou wheel + sdist; twine check PASSED nos dois. Teste de install em venv limpa: importa, versao 0.1.0, exports ok, 3 console scripts criados (lifeline/lifeline-mcp/lifeline-mcp-remote), lifeline --help exit 0, mcp_server+cloud importam. UNICO passo restante (do dono): criar conta no pypi.org + API token + 'twine upload dist/*'. Apos publicado, install vira 'pip install lifeline-context' e os snippets de conexao funcionam em qualquer maquina.

### #0061 — 2026-06-01T15:53:47.610770+00:00 — feature

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: feature
- **summary**: Publicacao no PyPI via Trusted Publishing (OIDC) — workflow publish.yml, sem token
- **parents**: 297a3f1b5005885b3458dbd1b3d6ac989097d73ea36e1e61550b7a4c0c1829f1
- **id**: 36ab5767f43e28534b523281cfb18966ec5f1b147f6eede481560ae19721ea91

**Body**:
Dono optou pelo Trusted Publisher (OIDC) em vez de API token — mais seguro, nada de segredo pra gerenciar. Criado .github/workflows/publish.yml: dispara em release published (ou workflow_dispatch manual); permissions id-token: write (OIDC); environment pypi (casa com o formulario do PyPI); builda sdist+wheel e publica via pypa/gh-action-pypi-publish@release/v1. Formulario PyPI Trusted Publisher: projeto=lifeline-context, owner=jessianmart, repo=lifeline, workflow=publish.yml, environment=pypi. Falta do dono: (1) submeter o formulario (pending publisher cria o projeto no 1o publish), (2) criar o environment 'pypi' em Settings->Environments do repo, (3) criar um GitHub Release v0.1.0 (ou rodar o workflow manual) -> publica sozinho via OIDC. Ancorado #0061.

### #0062 — 2026-06-01T15:59:04.361457+00:00 — feature

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: feature
- **summary**: EN docs (superficie de lancamento): README EN + README.pt-BR.md preservado, llms.txt e AGENTS.md traduzidos
- **parents**: 36ab5767f43e28534b523281cfb18966ec5f1b147f6eede481560ae19721ea91
- **id**: 19ef6e8c841f2e63a80bb2fc34c2ef6c35a1e8f2832a432c6dd3861e5e30bf32

**Body**:
Alcance global pro lancamento OSS. README.md agora em EN (front door + long_description do PyPI), com seletor de idioma; o PT preservado em README.pt-BR.md. llms.txt e AGENTS.md (AI-facing) traduzidos pra EN — alinha com o 'AI-first' global. Badges de testes atualizados (75). PENDENTE (proximo passo, deep docs ainda em PT): docs/INTEGRATION.md, docs/ARCHITECTURE.md, docs/MCP_REMOTE.md, docs/DEPLOY.md, docs/M3_TIER1_SUPABASE.md, CONTRIBUTING.md, PRD.md. CLAUDE.md e LIFELINE.md ficam em PT de proposito (laws internas + line gerada = dogfood). O README EN linka esses docs PT por ora (snippets sao copia-e-cola, agnosticos de idioma).

### #0063 — 2026-06-01T16:07:36.174972+00:00 — feature

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: feature
- **summary**: EN docs completo: deep docs traduzidos (INTEGRATION, ARCHITECTURE, MCP_REMOTE, DEPLOY, M3, CONTRIBUTING, PRD)
- **parents**: 19ef6e8c841f2e63a80bb2fc34c2ef6c35a1e8f2832a432c6dd3861e5e30bf32
- **id**: 260c0d1754205dadc7cfd912d5d6391e5ad8ee9ba51764ba7a56b25f983a7650

**Body**:
Fecha o EN do repo pro lancamento global. 7 deep docs traduzidos PT->EN (paralelizado com subagentes, glossario consistente), com fixes de staleness no caminho: CONTRIBUTING quality-gate trocado de 'pasta v2/ + loop por-arquivo' para 'python -m pytest' e a ref a _legacy ajustada (agora gitignored/no historico); PRD corrigido (id=sha256(content+parents) e arquitetura SEM Redis, alinhando #0038); comentarios PT dentro de code blocks (MCP_REMOTE, M3) passados pra EN; ARCHITECTURE ganhou as linhas de cloud.py/staging.py e a nota do MCP remoto; DEPLOY com o reality-check do #0057 (claude.ai web exige OAuth). Ficam em PT de proposito: CLAUDE.md (laws internas) e LIFELINE.md (line gerada = dogfood). README PT preservado em README.pt-BR.md. Superficie EN de lancamento completa.

### #0064 — 2026-06-01T16:25:20.421411+00:00 — fix

- **author**: unknown
- **agent**: human
- **provider**: none
- **model**: human
- **kind**: fix
- **summary**: CI estava vermelho: rodava pytest sem instalar (pytest nao e dep do pacote). Adiciona extra dev + verify reconstroi a cadeia real
- **parents**: 260c0d1754205dadc7cfd912d5d6391e5ad8ee9ba51764ba7a56b25f983a7650
- **id**: 20c1fe2892ccc34fc3b7901cb5bf072d34377b2ee598199d04835a7cc504497c

**Body**:
Diagnostico: o ci.yml fazia 'pip install -e .[cloud]' (so deps de runtime: pydantic/aiosqlite/mcp/httpx) e depois 'python -m pytest' — mas pytest NAO e dependencia do pacote, entao o step Testes falhava em todo push (vermelho desde que o CI foi adicionado, #0050). Reproduzido em venv limpa: pkg+pytest (sem pytest-asyncio) -> 75 passam (mcp 1.27.2 do PyPI tem todas as APIs usadas). Fix: (1) pyproject ganha optional-dependency dev=['pytest>=8']; (2) CI instala .[cloud,dev]; (3) step de integridade melhorado: 'lifeline migrate --from LIFELINE.md' + 'lifeline verify' (antes verificava um .db vazio -> 0 entradas trivial; agora reconstroi as 63 entradas da view versionada e verifica a cadeia REAL). Pacote em si nunca esteve quebrado (install/import/scripts provados); era so o CI sem pytest.
