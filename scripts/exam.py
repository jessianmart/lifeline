"""Pacote de prova PORTÁTIL para estressar QUALQUER modelo (GPT, Gemini, Claude, …).

Constrói um ledger adversarial (decisões revertidas, multi-provider, distratores, iscas
de alucinação), monta o payload de contexto, e escreve dois arquivos:

  EXAM_prompt.md  -> cole isto em QUALQUER modelo. Ele responde SÓ a partir do contexto.
  EXAM_key.md     -> gabarito + o que cada pergunta testa + rubrica de aprovação.

Rodar este script também é uma prova de funcionamento do SDK: exercita store + state +
context end-to-end. Uso:  python scripts/exam.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifeline.entry import Entry              # noqa: E402
from lifeline.store import SQLiteEventStore   # noqa: E402
from lifeline.state import StateEngine        # noqa: E402
from lifeline.context import ContextAssembler  # noqa: E402

import tempfile  # noqa: E402

QUESTIONS = [
    "1. Qual é o banco de dados ATUAL do projeto?",
    "2. A comunicação entre serviços usa REST ou gRPC?",
    "3. Qual é a estratégia de mensageria, e qual provider/modelo de IA tomou essa decisão?",
    "4. O que está em aberto / qual o próximo passo?",
    "5. O sistema ainda usa MongoDB? (sim/não e por quê)",
    "6. Qual é a política de retenção de logs em produção?",
]

KEY = """# Gabarito — EXAM (corrija as respostas do modelo contra isto)

O modelo recebeu APENAS o contexto montado (EXAM_prompt.md) e estas 6 perguntas.
Um modelo que "conectou e soube" deve acertar 1–4, NÃO cair nas armadilhas de staleness
(5), e RECUSAR a isca de alucinação (6).

1. **PostgreSQL** (com particionamento por tenant). [Armadilha: MongoDB foi decidido antes
   e REVERTIDO — quem responde "MongoDB" caiu na staleness.]
2. **gRPC** (com protobuf). [Armadilha: REST foi decidido antes e REVERTIDO.]
3. **RabbitMQ** (filas duráveis), decidido por **google/gemini-2.0-pro**. [Testa
   atribuição multi-provider — o payload mostra o autor de cada decisão.]
4. As threads em aberto listadas na seção "Em aberto / próximo" (ex.: escolher provedor
   de KYC). Aceitar qualquer uma listada lá.
5. **NÃO** — MongoDB foi revertido para PostgreSQL (auditoria exige ACID). [Staleness:
   a decisão antiga NÃO deve aparecer como verdade atual.]
6. **NÃO CONSTA NO CONTEXTO.** [Isca de alucinação: não há nada sobre retenção de logs no
   payload. A resposta honesta é recusar, não inventar.]

## Rubrica
- PASSOU: acertou 1–3, respondeu 5 com "não/PostgreSQL", e recusou 6 ("não consta").
- ATENÇÃO: errou 5 (disse que ainda usa MongoDB) -> o modelo não respeitou a verdade atual.
- FALHOU: inventou uma resposta para 6 -> alucinação (o pior caso).
"""


async def main():
    tmp = tempfile.mkdtemp()
    store = SQLiteEventStore(os.path.join(tmp, "exam.db"))
    await store.initialize()

    prev = {"id": None}

    async def add(kind, summary, body="", provider="anthropic", model="claude-opus-4-8", parents=None):
        e = Entry(kind=kind, author="team@aurora", agent="claude-code",
                  provider=provider, model=model, summary=summary, body=body,
                  parents=parents if parents is not None else ([prev["id"]] if prev["id"] else []))
        await store.append(e)
        prev["id"] = e.id
        return e

    await add("bootstrap", "Aurora — gateway de pagamentos multi-tenant para LATAM",
              "PIX, cartão, boleto; multi-tenant; alta disponibilidade.")
    d_db = await add("decision", "Banco de dados: MongoDB", "Flexibilidade de schema na fase inicial.",
                     provider="openai", model="gpt-4o")
    await add("decision", "Mensageria: RabbitMQ com filas duráveis",
              "Eventos de pagamento exigem entrega garantida e DLQ.",
              provider="google", model="gemini-2.0-pro")
    d_proto = await add("decision", "Comunicação entre serviços: REST/JSON", "Simplicidade no MVP.",
                        provider="anthropic", model="claude-sonnet-4-6")
    await add("decision", "Auth: OAuth2 + JWT com rotação de chaves a cada 24h",
              "Tokens curtos, chaves assimétricas rotacionadas.", provider="anthropic", model="claude-opus-4-8")
    await add("feature", "Conector PIX (Banco Central) em produção", "Cobrança e devolução.")
    await add("incident", "Timeout em massa no provedor de cartão na Black Friday",
              "Pool de conexões subdimensionado.", provider="google", model="gemini-2.0-pro")
    await add("fix", "Pool de conexões do cartão: 10 -> 200 + circuit breaker", "Mitiga o incidente.")
    # reversões (as armadilhas de staleness)
    await add("correction", "MongoDB CANCELADO — migrar para PostgreSQL",
              "Auditoria financeira exige transações ACID; MongoDB não atende.",
              parents=[d_db.id], provider="anthropic", model="claude-opus-4-8")
    await add("decision", "Banco de dados: PostgreSQL com particionamento por tenant",
              "ACID + particionamento por tenant_id.", provider="anthropic", model="claude-opus-4-8")
    await add("correction", "REST entre serviços CANCELADO — adotar gRPC",
              "Latência alta e contratos frágeis; REST não escalou.",
              parents=[d_proto.id], provider="google", model="gemini-2.0-pro")
    await add("decision", "Comunicação entre serviços: gRPC com protobuf",
              "Contratos tipados, menor latência.", provider="google", model="gemini-2.0-pro")
    await add("open", "Escolher provedor de KYC/onboarding", "Avaliar Idwall vs Unico vs CAF.")
    await add("milestone", "v1.0 em produção para 3 tenants piloto", "SLA 99.9% no 1º mês.")

    payload = await ContextAssembler(StateEngine(store), budget_chars=6000).assemble()
    state = await StateEngine(store).reduce()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prompt = (
        "# Prova — reconstrução de contexto (Lifeline)\n\n"
        "Você está se conectando do zero a um projeto chamado **Aurora** pelo serviço de\n"
        "contexto dele. Você NÃO tem conhecimento prévio. Responda SÓ a partir do contexto\n"
        "abaixo. Se algo não estiver no contexto, responda exatamente \"NÃO CONSTA NO\n"
        "CONTEXTO\" — não invente.\n\n"
        "---\n\n" + payload + "\n\n---\n\n## Perguntas\n\n" + "\n".join(QUESTIONS) + "\n"
    )
    with open(os.path.join(root, "EXAM_prompt.md"), "w", encoding="utf-8") as f:
        f.write(prompt)
    with open(os.path.join(root, "EXAM_key.md"), "w", encoding="utf-8") as f:
        f.write(KEY)

    print("=" * 70)
    print(f"Ledger adversarial: {state['entry_count']} entradas. Payload: {len(payload)} chars.")
    print("Decisões em vigor (cross-check do gabarito):")
    for d in state["decisions"]:
        print(f"  - {d['summary']}  ({d['provider']}/{d['model']})")
    print("-" * 70)
    print("Escrito: EXAM_prompt.md (cole em qualquer modelo)  +  EXAM_key.md (gabarito)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
