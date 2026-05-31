from typing import Dict, Any
from lifeline.engines.state_engine import StateEngine
from lifeline.engines.event_engine import EventEngine
from .episodic import EpisodicMemory
from .operational import OperationalMemory
from .semantic import SemanticMemory

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
