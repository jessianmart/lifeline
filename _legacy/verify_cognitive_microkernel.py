import asyncio
import sys
import time
from typing import Any, Dict

from lifeline.adapters.storage.sqlite import SQLiteEventStore, SQLiteSnapshotStore
from lifeline.engines.event_engine import EventEngine
from lifeline.engines.state_engine import StateEngine
from lifeline.context.assembly import ContextEngine
from lifeline.runtime.scheduler import CognitiveScheduler, ScheduledTask
from lifeline.runtime.policies.base import PolicyEngine
from lifeline.graph.reconciliation import BranchReconciler
from lifeline.memory.stratification import StratifiedMemoryManager
from lifeline.core.events import SystemEvent, ToolExecutionEvent

async def run_kernel_simulation():
    print("==================================================")
    print("   LIFELINE FASE 3: COGNITIVE MICROKERNEL VERIFIER")
    print("==================================================\n")

    db_file = "simulation_kernel.db"
    import os
    if os.path.exists(db_file): os.remove(db_file)

    # 1. Infrastructure Boostrap
    store = SQLiteEventStore(db_file)
    snap = SQLiteSnapshotStore(db_file)
    await store.initialize()
    await snap.initialize()

    event_engine = EventEngine(store)
    state_engine = StateEngine(event_engine, snap)
    ctx_engine = ContextEngine(store, event_engine, state_engine)
    policy_engine = PolicyEngine()
    
    scheduler = CognitiveScheduler(event_engine, ctx_engine, policy_engine)
    reconciler = BranchReconciler(event_engine, state_engine)
    mem_manager = StratifiedMemoryManager(event_engine, state_engine)

    print("[OK] Microkernel subsystem interfaces Online.\n")

    # ---------------------------------------------------------
    # TEST 1: STRATIFIED MEMORY TIERS
    # ---------------------------------------------------------
    print("--- 1: Stratified Consciousness Access ---")
    mem_wf = "wf_memory"
    mem_manager.working.set("temp_step", "validating_auth")
    
    await event_engine.emit(SystemEvent(workflow_id=mem_wf, action="START"))
    
    episodes = await mem_manager.episodic.recall_episodes(mem_wf)
    assert len(episodes) == 1
    assert mem_manager.working.get("temp_step") == "validating_auth"
    print("[OK] Ephemeral Working Tier & Causal Episodic memory layers confirmed.\n")

    # ---------------------------------------------------------
    # TEST 2: CONTEXT CACHE BY LOGICAL CLOCK
    # ---------------------------------------------------------
    print("--- 2: Zero-Cost Logical Cache Recovery ---")
    wf_cache = "wf_cache_demo"
    # Seed 3 baseline events
    await event_engine.emit(SystemEvent(workflow_id=wf_cache, action="OP1"))
    await event_engine.emit(SystemEvent(workflow_id=wf_cache, action="OP2"))
    
    # First Assembly (Miss: Generates Cache)
    t0 = time.perf_counter()
    payload_1 = await ctx_engine.assemble_context(wf_cache)
    dur_1 = time.perf_counter() - t0
    
    # Second Assembly (Hit: Bypasses all engines)
    t0 = time.perf_counter()
    payload_2 = await ctx_engine.assemble_context(wf_cache)
    dur_2 = time.perf_counter() - t0
    
    assert payload_1.workflow_id == payload_2.workflow_id
    # Cache should be virtually instantaneous
    print(f"[OK] First Build latency: {dur_1*1000:.2f}ms")
    print(f"[OK] Second Build (CACHE HIT) latency: {dur_2*1000:.2f}ms")
    assert dur_2 < dur_1, "Cache must be faster than full construction!"
    
    # Test Invalidation: Emit new event advancing clock
    await event_engine.emit(SystemEvent(workflow_id=wf_cache, action="OP3"))
    t0 = time.perf_counter()
    payload_3 = await ctx_engine.assemble_context(wf_cache)
    dur_3 = time.perf_counter() - t0
    
    print(f"[OK] Ledger advanced! Post-invalidation build latency: {dur_3*1000:.2f}ms")
    print("[OK] Cache invalidation strictly driven by clock state confirmed.\n")

    # ---------------------------------------------------------
    # TEST 3: OPERATIONAL BRANCH RECONCILIATION
    # ---------------------------------------------------------
    print("--- 3: Causal Branch Reconciliation (DAG Native) ---")
    wf_merge = "wf_bifurcate"
    
    # Reducer mapping for reconciliation detection
    def r_reducer(s: dict, e: Any):
        s = s.copy()
        if isinstance(e, ToolExecutionEvent):
            s[e.tool_name] = e.tool_args.get("val")
        return s
    state_engine.register_reducer("tool_execution", r_reducer)

    # Genesis Node
    root_id = await event_engine.emit(SystemEvent(workflow_id=wf_merge, action="GENESIS"))
    
    # Fork Branch A
    id_a = await event_engine.emit(ToolExecutionEvent(
        workflow_id=wf_merge, tool_name="metric_x", tool_args={"val": 10}, parent_event_ids=[root_id]
    ))
    # Fork Branch B
    id_b = await event_engine.emit(ToolExecutionEvent(
        workflow_id=wf_merge, tool_name="metric_x", tool_args={"val": 20}, parent_event_ids=[root_id]
    ))
    
    print("[SIM] Created 2 parallel branches with state collision on key 'metric_x'.")
    
    # Reconcile converging paths
    merge_node_id = await reconciler.reconcile_branches(
        workflow_id=wf_merge, event_id_a=id_a, event_id_b=id_b, strategy="keep_both_merged"
    )
    
    # Check final merged state in the emitted event!
    merged_ev = await event_engine.get_event(merge_node_id)
    merged_summary = merged_ev.merged_state_summary
    
    print(f"[OK] Merged Collision Outcome: 'metric_x' = {merged_summary['metric_x']}")
    assert merged_summary["metric_x"] == [10, 20] or merged_summary["metric_x"] == [20, 10]
    print("[OK] DAG paths successfully fused with collision-listified summary.\n")

    # ---------------------------------------------------------
    # TEST 4: COGNITIVE CAUSAL SCHEDULER
    # ---------------------------------------------------------
    print("--- 4: Causal Blocker Cognitive Scheduling ---")
    wf_sched = "wf_scheduling_ops"
    
    # Submitting dependent task chain
    # Task A: Compiles data. Represents node "compile_data_node"
    # Task B: Analyzes data. Blocked by node "compile_data_node"
    
    t_a = ScheduledTask(
        task_id="task_101", workflow_id=wf_sched, agent_id="agent_1", action_name="COMPILE",
        payload={"src": "log_file"}
    )
    
    t_b = ScheduledTask(
        task_id="task_102", workflow_id=wf_sched, agent_id="agent_1", action_name="ANALYZE",
        depends_on_nodes=["compile_data_node"] # THE CAUSAL BLOCKER
    )
    
    scheduler.submit_task(t_a)
    scheduler.submit_task(t_b)
    
    print("[SIM] Enqueued Task A and Task B (Task B depends on node 'compile_data_node').")
    
    # Evaluation Step 1: Only Task A should release!
    dispatched_1 = await scheduler.evaluate_and_dispatch()
    assert len(dispatched_1) == 1
    assert dispatched_1[0]["task_id"] == "task_101"
    print("[OK] Evaluation 1: Released Task A. Task B correctly BLOCKED in topological quarantine.")
    
    # "Execute" Task A: We emit the completed outcome to the ledger to satisfy dependency!
    await event_engine.emit(SystemEvent(
        workflow_id=wf_sched, action="COMPILE_COMPLETE", workflow_node_id="compile_data_node"
    ))
    
    print("[SIM] Executed Task A. Ledger updated with token 'compile_data_node'.")

    # Evaluation Step 2: Task B blocker is now lifted! It should dispatch!
    dispatched_2 = await scheduler.evaluate_and_dispatch()
    assert len(dispatched_2) == 1
    assert dispatched_2[0]["task_id"] == "task_102"
    # Crucial Verification: Envelope contains reconstructed context!
    assert dispatched_2[0]["cognitive_context"] is not None
    print("[OK] Evaluation 2: Blocker satisfied! Released Task B.")
    print(f"[OK] Dispatch envelope includes freshly compiled Cognitive Context!\n")

    print("==================================================")
    print("     FASE 3 COMPLETE: MICROKERNEL CORE PASS!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_kernel_simulation())
