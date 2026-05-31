from typing import List, Optional, Dict, Any
from lifeline.core.events import (
    EventBase, WorkflowState, FailureEvent, WorkflowStateTransitionEvent
)
from lifeline.runtime.state_machine import WorkflowStateMachine
from lifeline.engines.event_engine import EventEngine

class WorkflowContextCollector:
    """
    Synthesizes context derived from execution machinery status.
    If state is FAILED or RETRYING, extracts root failures to inject remedy traces.
    """
    def __init__(self, event_engine: EventEngine):
        self.engine = event_engine
        self.machine = WorkflowStateMachine(event_engine)

    async def collect_state_sensitive_context(self, workflow_id: str) -> Dict[str, Any]:
        """
        Audits WorkflowStateMachine and yields specialized directives based on current status.
        """
        current_status: WorkflowState = await self.machine.get_current_state(workflow_id)
        
        context_payload = {
            "current_status": current_status,
            "active_failures": []
        }

        # Actively retrieve root failure traces if workflow resides in an escalation state
        if current_status in ["RETRYING", "FAILED", "TIMEOUT"]:
            failures = []
            async for event in self.engine.get_workflow_stream(workflow_id):
                if isinstance(event, FailureEvent):
                    failures.append(event)
            
            # Map recent active failures to payload
            if failures:
                context_payload["active_failures"] = [
                    {
                        "domain": f.failure_domain,
                        "message": f.error_message,
                        "remedy_hint": f.contextual_remedy,
                        "clock": f.logical_clock
                    }
                    for f in failures[-3:] # Last 3 relevant failure instances
                ]

        return context_payload
