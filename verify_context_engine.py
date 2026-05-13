import asyncio
import sys
from typing import Any, Dict

from lifeline.adapters.storage.sqlite import SQLiteEventStore, SQLiteSnapshotStore
from lifeline.engines.event_engine import EventEngine
from lifeline.engines.state_engine import StateEngine
from lifeline.context.assembly import ContextEngine, ContextBudget
from lifeline.runtime.state_machine import WorkflowStateMachine
from lifeline.runtime.policies.base import PolicyEngine, ExecutionPolicyError
from lifeline.core.events import (
    SystemEvent, ToolExecutionEvent, FailureEvent, 
    AgentEvent, WorkflowStateTransitionEvent
)

async def run_simulation():
    print("==================================================")
    print("     LIFELINE FASE 2: CONTEXT & POLICY SIMULATION")
    print("==================================================\n")

    db_file = "simulation_context.db"
    import os
    if os.path.exists(db_file): os.remove(db_file)

    # 1. Infrastructure Startup
    store = SQLiteEventStore(db_file)
    snap_store = SQLiteSnapshotStore(db_file)
    await store.initialize()
    await snap_store.initialize()

    event_engine = EventEngine(store)
    state_engine = StateEngine(event_engine, snap_store)
    machine = WorkflowStateMachine(event_engine)
    policy_engine = PolicyEngine()
    
    # Custom Budget for crisp demo: maximum 5 events total
    budget = ContextBudget(max_events=5, max_failures=2)
    ctx_engine = ContextEngine(store, event_engine, state_engine, budget=budget)

    print("[1/4] Infra initialized. Causal substrate alive.\n")

    # ---------------------------------------------------------
    # TEST A: IDEMPOTENCY GUARD
    # ---------------------------------------------------------
    print("--- A: Idempotency Ledger Guard ---")
    dedup_key = "op_unique_ref_1000"
    
    # First emission
    id_a = await event_engine.emit(SystemEvent(
        workflow_id="wf_idemp", action="DEDUPLICATED_OP", deduplication_key=dedup_key
    ))
    
    # Attempt duplicate emission (should be ignored by DB constraints)
    id_b = await event_engine.emit(SystemEvent(
        workflow_id="wf_idemp", action="DEDUPLICATED_OP", deduplication_key=dedup_key
    ))

    # Query back to confirm count is exactly 1
    events = []
    async for ev in store.get_workflow_stream("wf_idemp"):
        events.append(ev)
        
    assert len(events) == 1, f"Should have exactly 1 event, got {len(events)}"
    print(f"[OK] Safely deduplicated operational event key: {dedup_key}")
    print(f"[OK] Ledger contains 1 unique execution of the duplicated operation.\n")

    # ---------------------------------------------------------
    # TEST B: POLICY SECURITY GUARDS (CAPABILITIES)
    # ---------------------------------------------------------
    print("--- B: Policy Engine & Capability Sandboxing ---")
    agent_id = "analyst_agent_007"
    
    # Try to execute superuser file tool
    required_caps = ["filesystem_write", "root"]
    
    try:
        policy_engine.verify_tool_execution(agent_id, "delete_root_dir", required_caps)
        print("[FAIL] Policy engine should have blocked execution!")
        sys.exit(1)
    except ExecutionPolicyError as e:
        print(f"[OK] Policy successfully BLOCKED execution. Reason: {e}")

    # Grant permissions and verify passing
    policy_engine.register_agent_capabilities(agent_id, ["filesystem_write", "root"])
    passed = policy_engine.verify_tool_execution(agent_id, "delete_root_dir", required_caps)
    assert passed is True
    print("[OK] Successfully authorized agent after capabilities elevated.\n")

    # ---------------------------------------------------------
    # TEST C: CONTEXT RECONSTRUCTION IN RETRYING STATE
    # ---------------------------------------------------------
    print("--- C: Operational Context vs RAG Reconstruction ---")
    wf_crash = "wf_cognitive_failure"
    
    # State reducer for demo
    def sample_reducer(state: Dict, event: Any):
        state = state.copy()
        if isinstance(event, ToolExecutionEvent) and not event.error:
             state["successful_steps"] = state.get("successful_steps", 0) + 1
        return state
    state_engine.register_reducer("tool_execution", sample_reducer)

    # 1. Successful Initial Chain
    await event_engine.emit(ToolExecutionEvent(
        workflow_id=wf_crash, tool_name="db_connector", tool_args={"port": 5432}
    ))
    await event_engine.emit(ToolExecutionEvent(
        workflow_id=wf_crash, tool_name="auth_validator", tool_args={"user": "guest"}
    ))
    
    # 2. DISASTER: INFRASTRUCTURE FAILURE
    # We register transition to FAILED manually for tracing
    await machine.transition(wf_crash, "READY", "INIT")
    await machine.transition(wf_crash, "RUNNING", "RUN")
    
    # Emit a raw failure event categorized in TOOL domain
    error_msg = "Permission Denied on write buffer /var/logs"
    await event_engine.emit(FailureEvent(
        workflow_id=wf_crash,
        failure_domain="TOOL",
        error_message=error_msg,
        contextual_remedy="Switch to fallback temporary directory or elevate permissions"
    ))
    
    # Escalate to RETRYING in StateMachine
    await machine.transition(wf_crash, "RETRYING", "TRIGGER_RECOVERY_LOOP")

    print(f"[SIM] Event chain generated. Workflow state is currently RETRYING.")
    
    # 3. Assemble the Cognitive Payload
    payload = await ctx_engine.assemble_context(wf_crash)

    # ---------------------------------------------------------
    # DISPLAY THE SUPREMACY OF LIFELINE CONTEXT OVER RAG
    # ---------------------------------------------------------
    print("\n>>> STANDARD RAG WOULD PROVIDE (Semantic similarity search):")
    print("    [Found 2 documents matching 'Permission Denied']: ")
    print("    1. 'How to setup folder permissions on Linux'")
    print("    2. 'Postgres user manual page 10'\n")

    print(">>> LIFELINE CONTEXT ENGINE PROVIDES (Operational Consciousness):")
    print("------------------------------------------------------------")
    print(payload.to_text_summary().strip())
    print("------------------------------------------------------------")

    # Assert integrity of dynamic injection
    assert payload.workflow_state == "RETRYING"
    assert len(payload.active_failures) == 1
    assert payload.active_failures[0]["domain"] == "TOOL"
    assert payload.reconstructed_state["successful_steps"] == 2
    # Asserts Budget limits worked (we limit to N events in budget)
    assert len(payload.compressed_causal_chain) <= 5
    
    print("\n[OK] Context payload fully matches mathematical reality.")
    print("[OK] Causal trace and state are fully active and coherent.\n")

    print("==================================================")
    print("       FASE 2 VERIFIED: PERFECT INTEGRATION!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_simulation())
