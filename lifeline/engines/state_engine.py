from typing import Callable, Dict, Optional, Any

from lifeline.core.events import EventBase
from lifeline.core.exceptions import StateReconstructionError
from lifeline.core.types import EventID
from lifeline.engines.event_engine import EventEngine
from lifeline.adapters.storage.base import AbstractSnapshotStore

# Type alias for a reducer function: (current_state, event) -> new_state
ReducerFunc = Callable[[Dict[str, Any], EventBase], Dict[str, Any]]

class StateEngine:
    """
    High-performance state rebuilder supporting incremental fast-forward recovery.
    Uses historical event sourcing reducers and retrieves snapshots to minimize replay lag.
    """

    def __init__(self, event_engine: EventEngine, snapshot_store: Optional[AbstractSnapshotStore] = None):
        self.event_engine = event_engine
        self.snapshot_store = snapshot_store
        self._reducers: Dict[str, ReducerFunc] = {}

    def register_reducer(self, event_type: str, reducer: ReducerFunc) -> None:
        """Registers a function to handle state transitions for a specific event type."""
        self._reducers[event_type] = reducer

    def _apply_event(self, state: Dict[str, Any], event: EventBase) -> Dict[str, Any]:
        """Applies a single event to the state using the registered reducer."""
        event_type = getattr(event, "event_type", "base")
        reducer = self._reducers.get(event_type)
        if reducer:
            try:
                # Return new dict to maintain functional immutability
                return reducer(state.copy() if state else {}, event)
            except Exception as e:
                raise StateReconstructionError(f"Error applying {event_type} (ID: {event.event_id}): {e}") from e
        return state

    async def rebuild_workflow_state(self, workflow_id: str, force_full_replay: bool = False) -> Dict[str, Any]:
        """
        Reconstructs workflow state efficiently.
        If a snapshot exists, retrieves it and replays ONLY subsequent events based on Lamport clock.
        """
        state = {}
        since_clock = -1
        
        # 1. Try fetching latest snapshot for immediate jumpstart
        if self.snapshot_store and not force_full_replay:
            snapshot = await self.snapshot_store.get_latest_snapshot(workflow_id)
            if snapshot:
                state = snapshot["state"]
                last_event_id = snapshot["last_event_id"]
                # Query actual event to extract its logical clock
                anchor_event = await self.event_engine.get_event(last_event_id)
                if anchor_event:
                    since_clock = anchor_event.logical_clock

        # 2. Efficiently fast-forward replay outstanding events
        async for event in self.event_engine.get_workflow_stream(workflow_id, since_logical_clock=since_clock):
            state = self._apply_event(state, event)
            
        return state

    async def rebuild_agent_state(self, agent_id: str, force_full_replay: bool = False) -> Dict[str, Any]:
        """
        Reconstructs agent state efficiently using incremental snapshots if available.
        """
        state = {}
        since_clock = -1
        
        if self.snapshot_store and not force_full_replay:
            snapshot = await self.snapshot_store.get_latest_snapshot(agent_id)
            if snapshot:
                state = snapshot["state"]
                last_event_id = snapshot["last_event_id"]
                anchor_event = await self.event_engine.get_event(last_event_id)
                if anchor_event:
                    since_clock = anchor_event.logical_clock

        async for event in self.event_engine.get_agent_stream(agent_id, since_logical_clock=since_clock):
            state = self._apply_event(state, event)
            
        return state

    async def rebuild_from_snapshot(self, snapshot_state: Dict[str, Any], events_since_snapshot: list[EventBase]) -> Dict[str, Any]:
        """Manually applies an ordered array of deltas onto an existing anchor."""
        state = snapshot_state.copy()
        for event in events_since_snapshot:
            state = self._apply_event(state, event)
        return state
