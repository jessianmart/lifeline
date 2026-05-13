import asyncio
import sys
from datetime import datetime
from typing import Any, Dict

from lifeline.adapters.storage.sqlite import SQLiteEventStore, SQLiteSnapshotStore
from lifeline.engines.event_engine import EventEngine
from lifeline.engines.state_engine import StateEngine
from lifeline.engines.snapshot_engine import SnapshotEngine
from lifeline.engines.replay_engine import ReplayEngine
from lifeline.core.events import (
    SystemEvent, ToolExecutionEvent, WorkflowStateTransitionEvent, 
    AgentEvent
)
from lifeline.core.exceptions import CausalIntegrityError, StateReconstructionError
from lifeline.runtime.state_machine import WorkflowStateMachine
from lifeline.graph.lineage import OperationalLineageGraph

async def run_suite():
    print("==================================================")
    print("      LIFELINE SDK HARDENING VERIFICATION SUITE")
    print("==================================================\n")
    
    db_file = "verify_hardening.db"
    
    # Clean previous DB if exists
    import os
    if os.path.exists(db_file):
        os.remove(db_file)

    # Initialize infrastructure
    store = SQLiteEventStore(db_file)
    snapshot_store = SQLiteSnapshotStore(db_file)
    await store.initialize()
    await snapshot_store.initialize()

    engine = EventEngine(store)
    state_engine = StateEngine(engine, snapshot_store)
    snapshot_engine = SnapshotEngine(snapshot_store, state_engine, engine)
    replay_engine = ReplayEngine(engine)
    graph = OperationalLineageGraph(store)
    state_machine = WorkflowStateMachine(engine)

    print("[Init] Lifeline Causal Ledger components online.\n")

    # ---------------------------------------------------------
    # TEST 1: Automatic Lamport Clock and Parent Chaining
    # ---------------------------------------------------------
    print("--- TEST 1: Lamport clock and parent chaining ---")
    wf_1 = "wf_lambda_100"
    e1_id = await engine.emit(SystemEvent(workflow_id=wf_1, action="INIT"))
    e2_id = await engine.emit(SystemEvent(workflow_id=wf_1, action="BOOT"))
    e3_id = await engine.emit(SystemEvent(workflow_id=wf_1, action="READY"))

    e1 = await engine.get_event(e1_id)
    e2 = await engine.get_event(e2_id)
    e3 = await engine.get_event(e3_id)

    assert e1.logical_clock == 0, "E1 clock must be 0"
    assert e2.logical_clock == 1, "E2 clock must be 1"
    assert e3.logical_clock == 2, "E3 clock must be 2"
    assert e2.parent_event_ids == [e1_id], "E2 must link to E1"
    assert e3.parent_event_ids == [e2_id], "E3 must link to E2"
    print("[OK] Lamport sequence correct: 0 -> 1 -> 2.")
    print("[OK] Direct causal ancestors confirmed.\n")

    # ---------------------------------------------------------
    # TEST 2: Causal Ledger Tampering / Breakage Detection
    # ---------------------------------------------------------
    print("--- TEST 2: Causal integrity validation ---")
    fake_parent = "sha256_fakehash999"
    broken_event = SystemEvent(workflow_id=wf_1, action="HACK", parent_event_ids=[fake_parent])
    
    try:
        await engine.emit(broken_event)
        print("[FAIL] Should have detected broken causal links!")
        sys.exit(1)
    except CausalIntegrityError as e:
        print(f"[OK] Successfully blocked broken causal chain. Details: {e}\n")

    # ---------------------------------------------------------
    # TEST 3: Operational Branch Forks & Convergent Joins (DAG Native)
    # ---------------------------------------------------------
    print("--- TEST 3: Operational branch forks & convergent joins ---")
    # We fork from e3
    branch_a_id = await engine.emit(SystemEvent(workflow_id=wf_1, action="FORK_BRANCH_A", parent_event_ids=[e3_id]))
    branch_b_id = await engine.emit(SystemEvent(workflow_id=wf_1, action="FORK_BRANCH_B", parent_event_ids=[e3_id]))
    
    a_ev = await engine.get_event(branch_a_id)
    b_ev = await engine.get_event(branch_b_id)
    
    assert a_ev.logical_clock == 3
    assert b_ev.logical_clock == 3
    print("[OK] Valid fork created. Both child events exist at clock index 3.")

    # Joint event merges both paths
    merge_id = await engine.emit(SystemEvent(
        workflow_id=wf_1, 
        action="CONVERGENCE", 
        parent_event_ids=[branch_a_id, branch_b_id]
    ))
    
    merge_ev = await engine.get_event(merge_id)
    assert merge_ev.logical_clock == 4, f"Joint clock should be 4, got {merge_ev.logical_clock}"
    assert set(merge_ev.parent_event_ids) == {branch_a_id, branch_b_id}
    print(f"[OK] Multi-parent join success. Joint clock: {merge_ev.logical_clock}.")
    
    # Test graph converge
    converged = await graph.find_convergent_ancestor(branch_a_id, branch_b_id)
    assert converged == e3_id
    print(f"[OK] Graph convergence identified common ancestor: {converged[:8]}...\n")

    # ---------------------------------------------------------
    # TEST 4: Structured State Machine Guards
    # ---------------------------------------------------------
    print("--- TEST 4: State Machine guards and invalid transitions ---")
    wf_2 = "wf_omega_state"
    
    # Initial state should be PENDING
    init_s = await state_machine.get_current_state(wf_2)
    assert init_s == "PENDING"
    
    # Legitimate shift: PENDING -> READY
    await state_machine.transition(wf_2, "READY", "VALIDATE_RESOURCES")
    # Legitimate shift: READY -> RUNNING
    await state_machine.transition(wf_2, "RUNNING", "START_COGNITIVE_CYCLE")
    
    curr = await state_machine.get_current_state(wf_2)
    assert curr == "RUNNING"
    print("[OK] Validated transitions: PENDING -> READY -> RUNNING.")

    # Illegal shift attempt: RUNNING -> ROLLEDBACK (not allowed directly)
    try:
        await state_machine.transition(wf_2, "ROLLEDBACK", "FORCED_UNDO")
        print("[FAIL] Should not allow RUNNING -> ROLLEDBACK direct transition!")
        sys.exit(1)
    except StateReconstructionError as e:
        print(f"[OK] Successfully blocked invalid transition. Details: {e}\n")

    # ---------------------------------------------------------
    # TEST 5: Fast-Forward Incremental Snapshots
    # ---------------------------------------------------------
    print("--- TEST 5: Fast-forward incremental snapshots ---")
    wf_3 = "wf_snap_ops"
    
    # Basic state reducer for verification: just counts tools called
    def test_reducer(s: dict, e: Any):
        s = s.copy()
        if isinstance(e, ToolExecutionEvent):
            s["tool_count"] = s.get("tool_count", 0) + 1
        return s

    state_engine.register_reducer("tool_execution", test_reducer)

    # 1. Emit 5 events
    for i in range(5):
        last_id = await engine.emit(ToolExecutionEvent(
            workflow_id=wf_3, tool_name="test_tool", tool_args={"step": i}
        ))

    # Rebuild state up to here
    initial_reconstructed = await state_engine.rebuild_workflow_state(wf_3)
    assert initial_reconstructed["tool_count"] == 5
    
    # 2. Save an incremental snapshot at index 5
    await snapshot_engine.create_snapshot(wf_3, initial_reconstructed, last_id)
    print("[OK] Created state snapshot at event count 5.")

    # 3. Emit 5 more events (total 10)
    for i in range(5, 10):
        await engine.emit(ToolExecutionEvent(
            workflow_id=wf_3, tool_name="test_tool", tool_args={"step": i}
        ))

    # 4. Rebuild final state
    # Internally, StateEngine reads the snapshot (tool_count = 5) and fetches 
    # ONLY outstanding events from SQL (which should be exactly 5 items instead of 10!)
    final_reconstructed = await state_engine.rebuild_workflow_state(wf_3)
    assert final_reconstructed["tool_count"] == 10
    print("[OK] Successfully reconstructed state using fast-forward: tool_count = 10.\n")

    # ---------------------------------------------------------
    # TEST 6: Deterministic Physical Replay (Mocks)
    # ---------------------------------------------------------
    print("--- TEST 6: Deterministic physical replay interception ---")
    wf_replay = "wf_to_replay"
    
    # Record external interaction
    t_id = await engine.emit(ToolExecutionEvent(
        workflow_id=wf_replay,
        tool_name="external_weather_api",
        tool_args={"city": "São Paulo"},
        tool_result={"temp": 18, "status": "Rainy"}
    ))

    # Prepare Mock Replay Session
    session = await replay_engine.start_physical_replay_session(wf_replay, replay_mode="mock")
    
    # Extract outcome as if re-executing tool
    intercepted = session.get_recorded_tool_result("external_weather_api", {"city": "São Paulo"})
    
    assert intercepted == {"temp": 18, "status": "Rainy"}
    print("[OK] Physical Replay successfully intercepted external dependency.")
    print(f"[OK] Retransmitted authentic historical payload: {intercepted}.\n")

    print("==================================================")
    print("       CONGRATULATIONS! ALL TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_suite())
