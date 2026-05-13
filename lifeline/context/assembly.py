from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from lifeline.adapters.storage.base import AbstractEventStore
from lifeline.engines.event_engine import EventEngine
from lifeline.engines.state_engine import StateEngine
from lifeline.core.events import EventBase, WorkflowState

from .retrieval import FederatedContextRetrieval
from .ranking import ContextRankingEngine
from .compression import ContextCompressionEngine, ContextBudget

class ContextPayload(BaseModel):
    """
    The structured Operational Cognitive Model.
    Acts as a substrate payload representing synthesized historical, 
    causal, and state awareness for LLMs and Planners.
    """
    workflow_id: str
    workflow_state: WorkflowState
    reconstructed_state: Dict[str, Any]
    compressed_causal_chain: List[EventBase]
    active_failures: List[Dict[str, Any]]
    
    # Versioning governance headers
    context_version: str = "1.0.0"
    assembly_version: str = "1.0.0"

    # Built-in lightweight utility for raw string conversion if presentation layer needed
    def to_text_summary(self) -> str:
        summary = f"Context Operational Summary [WF: {self.workflow_id}] [Ver: {self.context_version}]\n"
        summary += f"Current State: {self.workflow_state}\n"
        summary += f"Reconstructed System Memory: {self.reconstructed_state}\n"
        if self.active_failures:
            summary += f"\nCRITICAL FAILURES DETECTED:\n"
            for f in self.active_failures:
                summary += f" - Clock [{f['clock']}] [{f['domain']}]: {f['message']} (Remedy Hint: {f['remedy_hint']})\n"
        summary += f"\nCausal Events Lineage:\n"
        for e in self.compressed_causal_chain:
            summary += f" [{e.logical_clock}] {getattr(e, 'event_type', 'event')}: "
            if hasattr(e, 'action'): summary += f"Action={e.action} "
            if hasattr(e, 'tool_name'): summary += f"Tool={e.tool_name} "
            summary += f"({e.event_id[:8]}...)\n"
        return summary

class ContextEngine:
    """
    The Sovereign Reconstructor.
    Orchestrates full lifecycle: Cache query -> retrieval -> ranking -> compression -> payload assembly.
    Accelerates reconstruction to ZERO-cost using Logical Clock Caches.
    """
    def __init__(
        self, 
        store: AbstractEventStore, 
        event_engine: EventEngine, 
        state_engine: StateEngine,
        budget: Optional[ContextBudget] = None
    ):
        self.store = store
        self.retrieval = FederatedContextRetrieval(store, event_engine, state_engine)
        self.ranking = ContextRankingEngine()
        self.compression = ContextCompressionEngine(budget or ContextBudget())
        
        # Inject High-performance Logical Cache
        from .cache import AssembledContextCache
        self._cache = AssembledContextCache()

    async def assemble_context(self, workflow_id: str, current_event_id: Optional[str] = None) -> ContextPayload:
        """
        Retrieves, filters, and synthesizes the optimal operational cognitive model.
        Utilizes caching keyed deterministically by absolute logical clocks.
        """
        import time
        from lifeline.adapters.observability.profiler import kernel_profiler
        
        t_start = time.perf_counter()

        # 0. Determine the boundary of state via current logical clock for Cache evaluation
        latest_event = await self.store.get_latest_workflow_event(workflow_id)
        current_clock = latest_event.logical_clock if latest_event else -1
        
        # Version markers for algorithmic signature safety
        ctx_ver = "1.0.0"
        asmb_ver = "1.0.0"

        # Only check cache if we are fetching context for the actual head (no custom offset override)
        if not current_event_id:
            cached_payload = self._cache.get(workflow_id, current_clock, ctx_ver, asmb_ver)
            if cached_payload:
                # CACHE DETERMINISTIC HIT! We bypass Federated Query completely!
                t_end = time.perf_counter()
                kernel_profiler.record_context_assembly((t_end - t_start)*1000, is_hit=True)
                return cached_payload

        # Cache Miss - Proceed to full query reconstruction

        # 1. Federated Querying (Conductor)
        raw_materials = await self.retrieval.retrieve_raw_context(workflow_id, current_event_id)
        
        # 2. Signal Weighting & Boosts (Ranking)
        ranked = self.ranking.rank_and_score(raw_materials)
        
        # 3. Causal Summarization & Budget Limits (Compression)
        compressed = self.compression.compress(ranked, raw_materials["reconstructed_state"])
        
        # Extract cleanly structured items from compressed list
        clean_events = [f["event"] for f in compressed]
        
        # 4. Synthesize into structured Cognitive Payload
        payload = ContextPayload(
            workflow_id=workflow_id,
            workflow_state=raw_materials["status"]["current_status"],
            reconstructed_state=raw_materials["reconstructed_state"],
            compressed_causal_chain=clean_events,
            active_failures=raw_materials["status"]["active_failures"],
            context_version=ctx_ver,
            assembly_version=asmb_ver
        )
        
        # 5. Commit to Cache under deterministic anchor clock & algorithm version
        if not current_event_id:
            self._cache.set(workflow_id, current_clock, ctx_ver, asmb_ver, payload)
            
        t_end = time.perf_counter()
        kernel_profiler.record_context_assembly((t_end - t_start)*1000, is_hit=False)

        return payload
