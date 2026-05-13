from typing import Dict, List, Optional, Any
from datetime import datetime

from lifeline.core.events import WorkflowState, WorkflowStateTransitionEvent
from lifeline.engines.event_engine import EventEngine
from lifeline.core.exceptions import StateReconstructionError

class WorkflowStateMachine:
    """
    Formally executes validated, transactional workflow transitions.
    Defines and enforces strict guards and policies on current operational state.
    Emits formal StateTransition events to ensure auditable, immutable lineage.
    """
    
    # The strict directional DAG of valid operational state transitions
    VALID_TRANSITIONS: Dict[WorkflowState, List[WorkflowState]] = {
        "PENDING": ["READY", "CANCELLED"],
        "READY": ["RUNNING", "CANCELLED"],
        "RUNNING": ["WAITING", "RETRYING", "COMPLETED", "FAILED", "TIMEOUT", "CANCELLED"],
        "WAITING": ["RUNNING", "TIMEOUT", "CANCELLED"],
        "RETRYING": ["RUNNING", "CANCELLED"],
        # Terminal states usually permit nothing, but allow ROLLEDBACK manually
        "COMPLETED": ["ROLLEDBACK"],
        "FAILED": ["RETRYING", "ROLLEDBACK"],
        "CANCELLED": ["ROLLEDBACK"],
        "TIMEOUT": ["RETRYING", "ROLLEDBACK"],
        "ROLLEDBACK": ["READY"]
    }

    def __init__(self, event_engine: EventEngine):
        self.event_engine = event_engine

    async def get_current_state(self, workflow_id: str) -> WorkflowState:
        """Rebuilds current machine state by replaying transitions exclusively."""
        current: WorkflowState = "PENDING"
        
        async for event in self.event_engine.get_workflow_stream(workflow_id):
            if isinstance(event, WorkflowStateTransitionEvent):
                current = event.to_state
                
        return current

    async def transition(
        self, 
        workflow_id: str, 
        to_state: WorkflowState, 
        trigger: str, 
        metadata: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None
    ) -> WorkflowStateTransitionEvent:
        """
        Executes an auditable transactional state shift if allowed by guards.
        Automatically commits WorkflowStateTransitionEvent on success.
        """
        current = await self.get_current_state(workflow_id)
        
        # Enforce Guard Policies
        if current == to_state:
            # Idempotency: state remains identical
            pass 
        else:
            allowed = self.VALID_TRANSITIONS.get(current, [])
            if to_state not in allowed:
                raise StateReconstructionError(
                    f"Illegal State Machine Transition: Cannot move from {current} to {to_state}. "
                    f"(Trigger: {trigger})"
                )

        # Instantiate transaction event
        transition_event = WorkflowStateTransitionEvent(
            workflow_id=workflow_id,
            agent_id=agent_id,
            from_state=current,
            to_state=to_state,
            trigger=trigger,
            transition_metadata=metadata
        )
        
        # Commit directly to the immutable causal ledger via event engine
        await self.event_engine.emit(transition_event)
        return transition_event
