"""Camada 2 (operacional): colapsa o ledger na *verdade atual* via reducers.

Status é PROJEÇÃO de reducer sobre o stream — não uma máquina de estados de execução
(decisão #0002). Reducers são funções puras (estado, entry) -> estado, dobradas em
ordem causal. O reducer padrão `ledger_projection` entrega uma verdade útil de fábrica,
respeita correções (Lei #2: uma `correction` supersede seus pais) e carrega a autoria
(quem/qual provider/modelo) — proveniência que importa em contexto multiprovider.
"""
from typing import Any, Callable, Dict, List, Optional

from lifeline.entry import Entry
from lifeline.store import EventStore

Reducer = Callable[[Dict[str, Any], Entry], Dict[str, Any]]


def ledger_projection(state: Dict[str, Any], e: Entry) -> Dict[str, Any]:
    """Verdade-base: identidade, decisões em vigor, recentes, e autoria/proveniência."""
    s = dict(state)
    s["entry_count"] = s.get("entry_count", 0) + 1
    s["head"] = e.id

    kinds = dict(s.get("kinds", {}))
    kinds[e.kind] = kinds.get(e.kind, 0) + 1
    s["kinds"] = kinds

    # Autoria agregada: quem (provider/modelo) contribuiu, e quanto.
    by = f"{e.provider}/{e.model}"
    contributors = dict(s.get("contributors", {}))
    contributors[by] = contributors.get(by, 0) + 1
    s["contributors"] = contributors

    superseded = set(s.get("_superseded", set()))
    if e.kind == "correction":
        superseded.update(e.parents)
    s["_superseded"] = superseded
    s["superseded"] = sorted(superseded)  # exposto p/ o assembler marcar itens revertidos

    if e.kind == "bootstrap":
        s["project"] = e.summary
        s["project_by"] = by

    decisions = [d for d in s.get("decisions", []) if d["id"] not in superseded]
    if e.kind == "decision":
        decisions.append({
            "id": e.id, "summary": e.summary, "body": e.body,
            "provider": e.provider, "model": e.model, "agent": e.agent,
        })
    s["decisions"] = decisions

    # Threads em aberto: declaradas por `open`, fechadas quando uma entrada posterior
    # as supersede (mesmo mecanismo das correções — Lei #2).
    opens = [o for o in s.get("open_items", []) if o["id"] not in superseded]
    if e.kind == "open":
        opens.append({"id": e.id, "summary": e.summary})
    s["open_items"] = opens

    s["latest"] = (s.get("latest", []) + [{
        "id": e.id, "kind": e.kind, "summary": e.summary,
        "provider": e.provider, "model": e.model,
    }])[-5:]
    return s


class StateEngine:
    """Dobra o stream do ledger em estado consolidado, aplicando os reducers em ordem."""

    def __init__(self, store: EventStore, reducers: Optional[List[Reducer]] = None):
        self.store = store
        self._reducers: List[Reducer] = list(reducers) if reducers is not None else [ledger_projection]

    def register(self, reducer: Reducer) -> None:
        self._reducers.append(reducer)

    async def reduce(self) -> Dict[str, Any]:
        state: Dict[str, Any] = {}
        async for entry in self.store.stream():
            for r in self._reducers:
                state = r(state, entry)
        return {k: v for k, v in state.items() if not k.startswith("_")}
