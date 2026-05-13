from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from lifeline.engines.event_engine import EventEngine
from lifeline.context.assembly import ContextEngine, ContextPayload
from lifeline.runtime.policies.base import PolicyEngine, ExecutionPolicyError
from lifeline.runtime.resources import ResourceManager, ResourceExhaustionError

class ScheduledTask(BaseModel):
    """Representation of a Work Unit managed by the Cognitive Scheduler."""
    task_id: str
    workflow_id: str
    agent_id: str
    action_name: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    
    # Causal scheduler block list: WorkflowNodeIDs that MUST be satisfied before starting
    depends_on_nodes: List[str] = Field(default_factory=list)
    
    # Security policies: Required privileges to authorized dispatch
    required_capabilities: List[str] = Field(default_factory=list)

class CognitiveScheduler:
    """
    The Cognitive Master Core.
    Controls transactional execution streams. 
    Verifies causal topological blocks and policy clearances before injecting 
    fresh assembled context into work units for Dispatch.
    """
    def __init__(
        self, 
        event_engine: EventEngine, 
        context_engine: ContextEngine, 
        policy_engine: PolicyEngine,
        resource_manager: Optional[ResourceManager] = None
    ):
        self.engine = event_engine
        self.ctx_engine = context_engine
        self.policy_engine = policy_engine
        self.resource_manager = resource_manager or ResourceManager()
        
        # Pending task pools
        self._backlog: List[ScheduledTask] = []

    def submit_task(self, task: ScheduledTask) -> None:
        """Enqueues a cognitive task for evaluation and future dispatch."""
        self._backlog.append(task)

    async def evaluate_and_dispatch(self) -> List[Dict[str, Any]]:
        """
        Audits the backlog. Releases tasks whose causal and security predicates are fully met.
        Injects authentic reconstructed context into the dispatch envelope.
        """
        dispatched_envelopes = []
        remaining_backlog = []

        # Gather currently completed node tokens in ledger to evaluate blockers
        # In real runtime, we build a fast index, in MVP we query actual events
        completed_nodes = set()
        
        for task in self._backlog:
            # 1. AUDIT CAUSAL BLOCKERS
            # Query the stream to see which workflow_node_ids have finished
            # We'll check current completed nodes from ledger
            async for ev in self.engine.get_workflow_stream(task.workflow_id):
                if ev.workflow_node_id:
                    # We count presence in the ledger as fulfillment for simplicity in this MVP
                    completed_nodes.add(ev.workflow_node_id)
                    
            # Evaluate Blockers
            blocked = False
            for node in task.depends_on_nodes:
                if node not in completed_nodes:
                    blocked = True
                    break
                    
            if blocked:
                # Task resides in topological quarantine
                remaining_backlog.append(task)
                continue

            # 2. AUDIT POLICY CAPABILITIES
            try:
                self.policy_engine.verify_tool_execution(
                    task.agent_id, task.action_name, task.required_capabilities
                )
            except ExecutionPolicyError:
                # Deny Execution: Keep in backlog for administrative manual elevation / retry
                remaining_backlog.append(task)
                continue

            # 3. AUDIT RESOURCE BUDGET CEILINGS
            try:
                self.resource_manager.verify_dispatch_eligibility(task.agent_id)
            except ResourceExhaustionError:
                # Suspend execution under Resource Quarantine
                remaining_backlog.append(task)
                continue

            # 4. FUSE SITUATIONAL CONTEXT (Freshly reconstructed)
            # Generates zero-cost payload if cache hit occurs!
            payload: ContextPayload = await self.ctx_engine.assemble_context(task.workflow_id)

            # 5. CONSTRUCT ENVELOPE
            envelope = {
                "task_id": task.task_id,
                "action": task.action_name,
                "agent_id": task.agent_id,
                "payload": task.payload,
                "cognitive_context": payload
            }
            dispatched_envelopes.append(envelope)

        # 6. RECORD KERNEL METRICS (Introspection)
        from lifeline.adapters.observability.profiler import kernel_profiler
        
        # Distinguish between topological blocks and active dispatches
        blocked_count = len(remaining_backlog)
        pending_count = len(self._backlog)
        active_count = len(getattr(self.resource_manager, "_quotas", {}).keys())
        
        kernel_profiler.record_scheduler_tick(
            pending=pending_count,
            blocked=blocked_count,
            active_count=active_count
        )

        # Update active queue
        self._backlog = remaining_backlog
        return dispatched_envelopes
