"""Superfície MCP — a interface da IA é o produto (Lei #7).

  - LER ao conectar:  resource `lifeline://project/context` (a linha de vida montada) e
    a tool `lifeline_recall` (relevância ancorada).
  - PROPOR ao trabalhar:  tools `lifeline_append` / `lifeline_recontextualize` — a escrita
    da IA é HITL (human-in-the-loop): vira uma PROPOSTA pendente; um humano aprova via
    `lifeline review`/`approve` antes de entrar na line. Assim a IA dirige a captura sem
    poder sujar a verdade — quem cura é o humano (como aprovar um comando shell).

    LIFELINE_DB=.lifeline/ledger.db python -m lifeline.mcp_server
"""
import os

from mcp.server.fastmcp import FastMCP

from lifeline.cli import cmd_propose
from lifeline.context import ContextAssembler
from lifeline.state import StateEngine
from lifeline.store import SQLiteEventStore

mcp = FastMCP("Lifeline")
_DB = os.environ.get("LIFELINE_DB", os.path.join(".lifeline", "ledger.db"))
_AUTHOR = os.environ.get("LIFELINE_AUTHOR", "mcp")


@mcp.resource("lifeline://project/context")
async def project_context() -> str:
    """O contexto do projeto, montado e dentro do budget — leia isto ao conectar."""
    store = SQLiteEventStore(_DB)
    await store.initialize()
    return await ContextAssembler(StateEngine(store)).assemble()


@mcp.tool()
async def lifeline_append(kind: str, summary: str, body: str = "",
                          agent: str = "mcp-agent", provider: str = "none",
                          model: str = "unknown") -> str:
    """PROPÕE uma entrada (decisão/feature/fix/incident/milestone/note/open). Entra como
    PENDENTE — um humano aprova via `lifeline review`/`approve` antes de virar parte da line
    (HITL). O *porquê* importa mais que o *quê* — diga-o no body (obrigatório)."""
    try:
        pid = await cmd_propose(_DB, kind, summary, body, _AUTHOR, agent, provider, model, None)
    except ValueError as ex:
        return f"recusado: {ex}"
    return f"proposta #{pid} enfileirada ({kind}) — PENDENTE de aprovação humana (lifeline review)"


@mcp.tool()
async def lifeline_recontextualize(parent_id: str, summary: str, body: str = "",
                                   agent: str = "mcp-agent", provider: str = "none",
                                   model: str = "unknown") -> str:
    """PROPÕE uma correção que supersede a entrada `parent_id` (decisão revertida, thread
    fechada, fato atualizado). Append-only, nunca edição (Lei #2). Fica PENDENTE até um
    humano aprovar (HITL). Diga o *porquê* da mudança no body (obrigatório)."""
    try:
        pid = await cmd_propose(_DB, "correction", summary, body, _AUTHOR, agent, provider, model, [parent_id])
    except ValueError as ex:
        return f"recusado: {ex}"
    return f"correção proposta #{pid} (supersede {parent_id[:12]}) — PENDENTE de aprovação"


@mcp.tool()
async def lifeline_recall(query: str, k: int = 5) -> str:
    """Recupera as entradas mais RELEVANTES à tarefa atual (Camada 3 — ancoradas).
    Use para "já decidimos algo sobre X?" sem ler o ledger inteiro. Relevância, não recência."""
    from lifeline.recall import SemanticRecall
    store = SQLiteEventStore(_DB)
    await store.initialize()
    hits = await SemanticRecall(store).search(query, k=k)
    if not hits:
        return "Nada relevante encontrado no ledger."
    return "\n".join(
        f"[{h['kind']}] {h['summary']} (id={h['id'][:12]}, score={h['score']})" for h in hits
    )


def main():
    """Entry point (console script `lifeline-mcp`) — serve via stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
