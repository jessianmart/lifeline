from typing import Optional, Dict, Any

from lifeline.adapters.storage.base import AbstractSnapshotStore
from lifeline.core.types import EventID
from lifeline.engines.state_engine import StateEngine
from lifeline.engines.event_engine import EventEngine

class SnapshotEngine:
    """
    Manages taking and retrieving checkpoints of state to optimize rebuilding times.
    """

    def __init__(self, store: AbstractSnapshotStore, state_engine: StateEngine, event_engine: EventEngine):
        self.store = store
        self.state_engine = state_engine
        self.event_engine = event_engine

    async def create_snapshot(self, entity_id: str, current_state: Dict[str, Any], last_event_id: EventID, snapshot_type: str = "state") -> None:
        """
        Saves the current state as a robustly dimensioned snapshot (state, workflow, memory, context).
        """
        await self.store.save_snapshot(entity_id, current_state, last_event_id, snapshot_type=snapshot_type)

    async def get_latest_snapshot(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the latest snapshot metadata & state for an entity.
        """
        return await self.store.get_latest_snapshot(entity_id)
