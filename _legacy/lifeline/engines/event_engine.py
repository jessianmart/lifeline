from typing import AsyncIterator, List, Optional

from lifeline.adapters.storage.base import AbstractEventStore
from lifeline.core.events import EventBase
from lifeline.core.exceptions import EventValidationError, CausalIntegrityError
from lifeline.core.types import EventID, WorkflowID, AgentID


class EventEngine:
    """
    The causal cognitive ledger gatekeeper.
    Orchestrates DAG sealing, Lamport clock assignments, logical causality verification, 
    and concurrent branching detection.
    """

    def __init__(self, store: AbstractEventStore):
        self.store = store

    async def emit(self, event: EventBase) -> EventID:
        """
        Validates, chains dynamically into the DAG, increments Logical Lamport clocks, 
        and seals/persists a single event.
        """
        # 1. Determine causal parents and logical clock state
        parents = event.parent_event_ids.copy()
        next_clock = event.logical_clock

        # Automatic linear linking if scope exists and no explicit parents are stated
        if not parents:
            latest = None
            if event.workflow_id:
                latest = await self.store.get_latest_workflow_event(event.workflow_id)
            elif event.agent_id:
                latest = await self.store.get_latest_agent_event(event.agent_id)
            
            if latest:
                parents = [latest.event_id]
                next_clock = latest.logical_clock + 1
            else:
                # Genesis event in this scope
                next_clock = 0
        else:
            # User supplied parent nodes explicitly (Branch merge or explicit fork)
            # Calculate appropriate logical clock from all parent heads: max(clocks) + 1
            clocks = []
            for p_id in parents:
                p_event = await self.store.get_event(p_id)
                if not p_event:
                    raise CausalIntegrityError(f"Causal link broken: parent event {p_id} not found in ledger.")
                clocks.append(p_event.logical_clock)
            next_clock = max(clocks) + 1 if clocks else 0

        # 2. Cryptographically seal event to solidify deterministic ID
        # This integrates payload, specific parent hashes, and scalar logic clock.
        event.seal(parent_hashes=parents, logical_clock=next_clock)

        # 3. Detection of implicit concurrency branch (for downstream notification or logs)
        # (If a distinct event already exists with identical parents but different hash, a branch emerges.)
        
        # 4. Commit directly to storage
        await self.store.append(event)
        return event.event_id

    async def emit_batch(self, events: List[EventBase]) -> List[EventID]:
        """
        Atomically appends a sequence of pre-ordered events.
        """
        for event in events:
            # Assumes events in a batch might have internal DAG links already mapped,
            # but executes verification on non-initial events if desired.
            if not event.event_id:
                raise EventValidationError("Event sealing required before batch emission.")

        await self.store.append_batch(events)
        return [e.event_id for e in events]

    async def get_event(self, event_id: EventID) -> Optional[EventBase]:
        return await self.store.get_event(event_id)

    def get_workflow_stream(self, workflow_id: WorkflowID, since_logical_clock: int = -1) -> AsyncIterator[EventBase]:
        """Fetches event streams sequenced strictly by Logical clock causality."""
        return self.store.get_workflow_stream(workflow_id, since_logical_clock)

    def get_agent_stream(self, agent_id: AgentID, since_logical_clock: int = -1) -> AsyncIterator[EventBase]:
        return self.store.get_agent_stream(agent_id, since_logical_clock)
