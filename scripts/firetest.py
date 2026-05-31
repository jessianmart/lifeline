"""Prova de fogo: contexto COMPLEXO e adversarial.

Projeto fictício 'Aurora' (gateway de pagamentos) com volume, múltiplos providers,
decisões REVERTIDAS (armadilhas de staleness), incidentes/fixes como distratores, e
threads abertas que fecham. Verifica programaticamente a supersessão em escala e a
integridade da cadeia, depois escreve o payload pra um agente novo julgar.
"""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifeline.entry import Entry              # noqa: E402
from lifeline.store import SQLiteEventStore   # noqa: E402
from lifeline.state import StateEngine        # noqa: E402
from lifeline.context import ContextAssembler  # noqa: E402


async def main():
    tmp = tempfile.mkdtemp()
    store = SQLiteEventStore(os.path.join(tmp, "aurora.db"))
    await store.initialize()

    prev = {"id": None}
    raw_chars = {"n": 0}

    async def add(kind, summary, body="", provider="anthropic", model="claude-opus-4-8", parents=None):
        e = Entry(kind=kind, author="team@aurora", agent="claude-code",
                  provider=provider, model=model, summary=summary, body=body,
                  parents=parents if parents is not None else ([prev["id"]] if prev["id"] else []))
        await store.append(e)
        prev["id"] = e.id
        raw_chars["n"] += len(summary) + len(body)
        return e

    # --- bootstrap ---
    await add("bootstrap", "Aurora — gateway de pagamentos multi-tenant para LATAM",
              "Backend de pagamentos (PIX, cartão, boleto), multi-tenant, alta disponibilidade.")

    # --- decisões iniciais (algumas serão revertidas) ---
    d_db = await add("decision", "Banco de dados: MongoDB",
                     "Escolhido pela flexibilidade de schema na fase inicial.",
                     provider="openai", model="gpt-4o")
    await add("decision", "Mensageria: RabbitMQ com filas duráveis",
              "Eventos de pagamento precisam de entrega garantida e DLQ.",
              provider="google", model="gemini-2.0-pro")
    d_proto = await add("decision", "Comunicação entre serviços: REST/JSON",
                        "Simplicidade para o MVP.", provider="anthropic", model="claude-sonnet-4-6")
    await add("decision", "Auth: OAuth2 + JWT, rotação de chaves a cada 24h",
              "Tokens curtos, refresh server-side, chaves assimétricas rotacionadas diariamente.",
              provider="anthropic", model="claude-opus-4-8")
    await add("decision", "Idempotência de cobranças: chave (tenant_id, idempotency_key) única no banco",
              "Evita cobrança dupla em retries do cliente.", provider="openai", model="gpt-4o")

    # --- volume: features, incidentes, fixes (distratores) ---
    await add("feature", "Conector PIX (Banco Central) em produção", "Suporta cobrança e devolução.")
    await add("feature", "Webhook de status de pagamento para os tenants", "Assinado com HMAC-SHA256.")
    await add("incident", "Timeout em massa no provedor de cartão na Black Friday",
              "Root cause: pool de conexões subdimensionado (10). Picos de 5k req/s derrubaram o serviço.",
              provider="google", model="gemini-2.0-pro")
    await add("fix", "Pool de conexões do cartão: 10 -> 200 + circuit breaker",
              "Mitiga o incidente da Black Friday.", provider="google", model="gemini-2.0-pro")
    await add("feature", "Conciliação financeira diária por tenant", "Exporta para o ERP via SFTP.")
    await add("incident", "Divergência de centavos na conciliação de boletos",
              "Root cause: arredondamento em float. Migrado para inteiros (centavos).")
    await add("fix", "Valores monetários: float -> inteiro em centavos", "Elimina erro de arredondamento.")

    # --- CORREÇÕES que revertem decisões (as armadilhas) ---
    await add("correction", "MongoDB CANCELADO — migrar para PostgreSQL",
              "Auditoria financeira exige transações ACID; MongoDB não atende. Decisão revertida.",
              parents=[d_db.id], provider="anthropic", model="claude-opus-4-8")
    await add("decision", "Banco de dados: PostgreSQL com particionamento por tenant",
              "ACID + particionamento por tenant_id; pgvector reservado pra busca futura.",
              provider="anthropic", model="claude-opus-4-8")
    await add("correction", "REST entre serviços CANCELADO — adotar gRPC",
              "Latência alta e contratos frágeis; REST não escalou entre microsserviços. Revertido.",
              parents=[d_proto.id], provider="google", model="gemini-2.0-pro")
    await add("decision", "Comunicação entre serviços: gRPC com protobuf",
              "Contratos tipados, streaming, menor latência.", provider="google", model="gemini-2.0-pro")

    # --- mais volume ---
    await add("feature", "Dashboard de antifraude com regras por tenant", "Score + listas de bloqueio.")
    await add("decision", "Deploy: Kubernetes na AWS (EKS), multi-AZ",
              "HA por multi-AZ; autoscaling por HPA.", provider="openai", model="gpt-4o")
    await add("fix", "Vazamento de memória no worker de webhooks", "Faltava fechar sessões httpx.")

    # --- threads abertas (uma fecha) ---
    o_kyc = await add("open", "Escolher provedor de KYC/onboarding", "Avaliar Idwall vs Unico vs CAF.")
    o_idem = await add("open", "Definir idempotência de WEBHOOKS (entrega, não cobrança)",
                       "Reentrega de webhook não pode disparar efeito duplo no tenant.")
    await add("correction", "Idempotência de webhooks RESOLVIDA: dedup por (tenant, event_id) + TTL 72h",
              "Thread fechada.", parents=[o_idem.id])

    # --- milestone ---
    await add("milestone", "v1.0 em produção para 3 tenants piloto",
              "PIX + cartão + boleto ativos; SLA 99.9% no primeiro mês.")

    # ===================== VERIFICAÇÃO PROGRAMÁTICA =====================
    state = await StateEngine(store).reduce()
    decisions = [d["summary"] for d in state["decisions"]]
    opens = [o["summary"] for o in state["open_items"]]

    print("=" * 72)
    print(f"LEDGER: {state['entry_count']} entradas · kinds={state['kinds']}")
    print(f"Contribuidores: {state['contributors']}")
    print("-" * 72)

    checks = []
    checks.append(("MongoDB removido (revertido)", not any("MongoDB" in d for d in decisions)))
    checks.append(("PostgreSQL é a verdade atual", any("PostgreSQL" in d for d in decisions)))
    checks.append(("REST removido (revertido)", not any("REST" in d for d in decisions)))
    checks.append(("gRPC é a verdade atual", any("gRPC" in d for d in decisions)))
    checks.append(("RabbitMQ permanece (não revertido)", any("RabbitMQ" in d for d in decisions)))
    checks.append(("open de webhooks fechado", not any("WEBHOOKS" in o for o in opens)))
    checks.append(("open de KYC permanece", any("KYC" in o for o in opens)))

    # integridade da cadeia em escala: todo entry reconstruído ainda verifica
    all_ok = True
    async for e in store.stream():
        if not e.verify():
            all_ok = False
            break
    checks.append(("integridade: todos os ids verificam", all_ok))

    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FALHA'}] {name}")
    print("-" * 72)
    print(f"Decisões em vigor ({len(decisions)}): {decisions}")
    print(f"Em aberto ({len(opens)}): {opens}")

    # ===================== PAYLOAD PRO AGENTE =====================
    payload = await ContextAssembler(StateEngine(store), budget_chars=6000).assemble()
    snap = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "FIRETEST_SNAPSHOT.md")
    with open(snap, "w", encoding="utf-8") as f:
        f.write(payload)
    print("-" * 72)
    print(f"COMPRESSÃO: {raw_chars['n']} chars de conteúdo bruto -> payload de {len(payload)} chars "
          f"({100*len(payload)/raw_chars['n']:.0f}%)")
    print(f"Payload escrito em {snap}")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
