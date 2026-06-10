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


def _effective_superseded(corrections: List[Dict[str, Any]]) -> set:
    """Conjunto superseded EFETIVO, derivado do grafo de correções por ponto-fixo.

    Antes (gap #G8) `superseded` era um set que só CRESCIA: reverter uma reversão não
    restaurava o original e "supersessão em cadeia" corrompia. Aqui uma correção só
    SUPERSEDE enquanto ela própria está ATIVA; se outra correção a supersede, ela some
    e os pais dela voltam. Itera até estabilizar (some/volta converge — o grafo é finito).

    `corrections`: lista de {id, parents} na ordem do ledger.
    """
    ids = {c["id"] for c in corrections}
    active = set(ids)
    while True:
        superseded = set()
        for c in corrections:
            if c["id"] in active:
                superseded.update(c["parents"])
        new_active = {cid for cid in ids if cid not in superseded}
        if new_active == active:
            return superseded
        active = new_active


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

    # Acumula CRU (nunca poda na hora): supersessão pode reverter (gap #G8), então a
    # verdade-em-vigor é DERIVADA do grafo no fim, não construída por poda incremental.
    corrections = list(s.get("_corrections", []))
    if e.kind == "correction":
        corrections.append({"id": e.id, "parents": list(e.parents)})
    s["_corrections"] = corrections

    decisions_all = list(s.get("_decisions_all", []))
    if e.kind == "decision":
        decisions_all.append({
            "id": e.id, "summary": e.summary, "body": e.body,
            "provider": e.provider, "model": e.model, "agent": e.agent,
        })
    s["_decisions_all"] = decisions_all

    opens_all = list(s.get("_opens_all", []))
    if e.kind == "open":
        opens_all.append({"id": e.id, "summary": e.summary})
    s["_opens_all"] = opens_all

    if e.kind == "bootstrap":
        s["project"] = e.summary
        s["project_by"] = by

    # Deriva a verdade-em-vigor do grafo. Filtra por id superseded — vale mesmo se a
    # decisão chegou DEPOIS da correção (gap #G4: reordenação no stream não a ressuscita).
    superseded = _effective_superseded(corrections)
    s["superseded"] = sorted(superseded)
    s["decisions"] = [d for d in decisions_all if d["id"] not in superseded]
    s["open_items"] = [o for o in opens_all if o["id"] not in superseded]

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
        """Dobra o stream em estado. Gap #G3: VERIFICA a âncora de cada entrada antes de
        fundi-la — conteúdo adulterado no `.db` (id não bate com o conteúdo) é descartado da
        verdade (fail-safe, nunca servido como decisão) e listado em `integrity_broken` para
        o assembler avisar. `ts` segue fora do hash (Lei #3) — adulterar o relógio NÃO é
        coberto aqui; é limite declarado do produto (use o git como notário externo)."""
        state: Dict[str, Any] = {}
        broken: List[str] = []
        async for entry in self.store.stream():
            if not entry.verify():
                broken.append(entry.id)
                continue  # não funde conteúdo adulterado na verdade
            for r in self._reducers:
                state = r(state, entry)
        if broken:
            state["integrity_broken"] = broken
        return {k: v for k, v in state.items() if not k.startswith("_")}
