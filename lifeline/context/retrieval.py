from typing import Dict, Any, Optional, List
from lifeline.adapters.storage.base import AbstractEventStore
from lifeline.engines.event_engine import EventEngine
from lifeline.engines.state_engine import StateEngine

from .causality import CausalContextCollector
from .temporal import TemporalContextCollector
from .workflow import WorkflowContextCollector

class FederatedContextRetrieval:
    """
    Federated retrieval conductor.
    Interviews all context facets (causality, time, state, and memory) 
    to reconstruct the holistic operational reality.
    """
    def __init__(self, store: AbstractEventStore, event_engine: EventEngine, state_engine: StateEngine):
        self.store = store
        self.event_engine = event_engine
        self.state_engine = state_engine
        
        # Initialize dedicated sub-collectors
        self.causal_collector = CausalContextCollector(store)
        self.temporal_collector = TemporalContextCollector(event_engine)
        self.workflow_collector = WorkflowContextCollector(event_engine)

    async def retrieve_raw_context(self, workflow_id: str, current_event_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Performs concurrent multi-dimensional queries to retrieve the raw materials of context.
        """
        # 1. Get Active Engine/State status
        status_context = await self.workflow_collector.collect_state_sensitive_context(workflow_id)
        
        # 2. Get Chronological sequence
        temporal_events = await self.temporal_collector.collect_recent_chain(workflow_id, count=8)
        
        # 3. Get Graph Causal Ancestry (from the head of the ledger if current_event_id omitted)
        target_head = current_event_id
        if not target_head:
            latest = await self.store.get_latest_workflow_event(workflow_id)
            target_head = latest.event_id if latest else None
            
        causal_chain = []
        if target_head:
            causal_chain = await self.causal_collector.collect_causal_ancestry(target_head, max_depth=8)

        # 4. Rebuild operational memory (Current state snapshot)
        reconstructed_state = await self.state_engine.rebuild_workflow_state(workflow_id)

        return {
            "workflow_id": workflow_id,
            "status": status_context,
            "chronological_trace": temporal_events,
            "causal_ancestry": causal_chain,
            "reconstructed_state": reconstructed_state
        }
