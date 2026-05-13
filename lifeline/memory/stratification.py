from typing import Dict, Any, List, Optional
from lifeline.core.events import EventBase
from lifeline.engines.state_engine import StateEngine
from lifeline.engines.event_engine import EventEngine

class WorkingMemory:
    """Tier 1: Ephemeral local context of the active cognitive step."""
    def __init__(self):
        self._volatile_store: Dict[str, Any] = {}

    def set(self, key: str, val: Any) -> None:
        self._volatile_store[key] = val

    def get(self, key: str, default: Any = None) -> Any:
        return self._volatile_store.get(key, default)

    def clear(self) -> None:
        self._volatile_store.clear()

class EpisodicMemory:
    """Tier 2: Immutable serial trace of historical ledger actions."""
    def __init__(self, event_engine: EventEngine):
        self.engine = event_engine

    async def recall_episodes(self, workflow_id: str) -> List[EventBase]:
        episodes = []
        async for ev in self.engine.get_workflow_stream(workflow_id):
            episodes.append(ev)
        return episodes

class OperationalMemory:
    """Tier 3: Current consolidated system memory and fast recovery state."""
    def __init__(self, state_engine: StateEngine):
        self.engine = state_engine

    async def recall_operational_state(self, workflow_id: str) -> Dict[str, Any]:
        return await self.engine.rebuild_workflow_state(workflow_id)

class SemanticMemory:
    """Tier 4: Long-term associations and conceptual similarity pointers (lite)."""
    def __init__(self):
        self._semantic_associations: Dict[str, List[str]] = {}

    def associate(self, concept: str, node_id: str) -> None:
        self._semantic_associations.setdefault(concept.lower(), []).append(node_id)

    def find_similar_nodes(self, concept: str) -> List[str]:
        return self._semantic_associations.get(concept.lower(), [])

class StratifiedMemoryManager:
    """
    Unifies all levels of AI consciousness into a single access structure.
    Resolves queries to the optimal layer (Working -> Episodic -> Operational -> Semantic).
    """
    def __init__(self, event_engine: EventEngine, state_engine: StateEngine):
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory(event_engine)
        self.operational = OperationalMemory(state_engine)
        self.semantic = SemanticMemory()
