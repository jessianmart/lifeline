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
from lifeline.runtime.resources import ResourceManager, ResourceQuota, ResourceExhaustionError
from lifeline.runtime.process import AgentProcess
from lifeline.runtime.sandbox import IsolatedSandboxExecutor
from lifeline.core.events import SystemEvent

async def run_hypervisor_simulation():
    print("==================================================")
    print("    LIFELINE FASE 4: COGNITIVE HYPERVISOR PANEL")
    print("==================================================\n")

    db_file = "simulation_hypervisor.db"
    import os
    if os.path.exists(db_file): os.remove(db_file)

    # 1. Substrate Bootstrap
    store = SQLiteEventStore(db_file)
    await store.initialize()

    event_engine = EventEngine(store)
    state_engine = StateEngine(event_engine, None)
    ctx_engine = ContextEngine(store, event_engine, state_engine)
    policy_engine = PolicyEngine()
    
    # Inject Hypervisor Core Infrastructure
    res_manager = ResourceManager()
    scheduler = CognitiveScheduler(event_engine, ctx_engine, policy_engine, resource_manager=res_manager)
    sandbox = IsolatedSandboxExecutor(res_manager)

    print("[OK] Hypervisor physical coordination infrastructure Online.\n")

    # ---------------------------------------------------------
    # TEST 1: AGENT PROCESS MODEL LIFECYCLE
    # ---------------------------------------------------------
    print("--- 1: Agent Process Control Block Lifecycle ---")
    wf_pid = "wf_process_thread"
    agent_id = "orchestrator_v1"
    
    process = AgentProcess(pid="PID_9901", agent_id=agent_id, workflow_id=wf_pid, event_engine=event_engine)
    
    # Spawn -> Run -> Terminate Chain
    print("[SIM] Executing OS System Calls for Process ID 'PID_9901':")
    await process.spawn()
    print(f" -> [SPAWN] State: {process.pcb.state}")
    assert process.pcb.state == "SPAWNED"
    
    await process.run()
    print(f" -> [RUN] State: {process.pcb.state}")
    assert process.pcb.state == "RUNNING"
    
    await process.terminate()
    print(f" -> [TERMINATE] State: {process.pcb.state}\n")
    assert process.pcb.state == "TERMINATED"

    process_events = []
    async for ev in store.get_workflow_stream(wf_pid):
        process_events.append(ev.action)
        
    print(f"[OK] Ledger registered physical process sequence: {process_events}")
    assert "PROCESS_SPAWNED" in process_events
    assert "PROCESS_TERMINATED" in process_events
    print("[OK] Full process lifecycle trace committed replayably.\n")

    # ---------------------------------------------------------
    # TEST 2: ISOLATED TELEMETRY & SANDBOX EXECUTOR
    # ---------------------------------------------------------
    print("--- 2: Execution Sandboxing & Hardware Account Metering ---")
    agent_sb = "worker_agent_01"
    
    # Assign Resource Quotas: 500 tokens max
    res_manager.provision_quota(agent_sb, ResourceQuota(max_tokens=500, max_execution_ms=5000))
    
    def sample_tool(data: str) -> str:
        time.sleep(0.05) # Simulate 50ms IO lag
        return f"Processed {data.upper()}"

    print(f"[SIM] Dispatching tool execution into Isolated Sandbox Executor...")
    result, telemetry = await sandbox.execute_sandboxed_tool(
        agent_id=agent_sb,
        tool_callable=sample_tool,
        tool_args={"data": "core_system_logs"}
    )
    
    print(f"[OK] Tool Result: {result}")
    print(f"[OK] Telemetry Account: CPU Time={telemetry.execution_time_ms}ms, Tokens={telemetry.tokens_consumed}")
    assert telemetry.execution_time_ms >= 40
    assert telemetry.tokens_consumed > 50
    
    quota = res_manager.get_quota(agent_sb)
    print(f"[OK] ResourceManager Quota Remaining: {quota.max_tokens - quota.consumed_tokens} tokens.\n")
    
    # ---------------------------------------------------------
    # TEST 3: RESOURCE EXHAUSTION & SOFT SUSPEND (CONTINUITY)
    # ---------------------------------------------------------
    print("--- 3: Resource Depletion Soft Suspend & Continuity Recovery ---")
    wf_depletion = "wf_budget_drain"
    agent_drain = "miner_agent_88"
    
    res_manager.provision_quota(agent_drain, ResourceQuota(max_tokens=100))
    
    proc_drain = AgentProcess(pid="PID_1100", agent_id=agent_drain, workflow_id=wf_depletion, event_engine=event_engine)
    await proc_drain.spawn()
    await proc_drain.run()
    
    # Enqueue tasks in Scheduler
    # Task B DEPENDS ON Task A finishing! Ensures sequential evaluation natively.
    t_a = ScheduledTask(task_id="task_a", workflow_id=wf_depletion, agent_id=agent_drain, action_name="TASK_A")
    t_b = ScheduledTask(
        task_id="task_b", workflow_id=wf_depletion, agent_id=agent_drain, action_name="TASK_B",
        depends_on_nodes=["task_a_done"] # Topological causal constraint
    )
    
    scheduler.submit_task(t_a)
    scheduler.submit_task(t_b)

    # 1st Evaluation: Task A will pass eligibility. Task B blocked by CAUSAL constraint.
    dispatched_1 = await scheduler.evaluate_and_dispatch()
    print(f"[DEBUG] Released on Eval 1: {[t['task_id'] for t in dispatched_1]}")
    assert len(dispatched_1) == 1
    assert dispatched_1[0]["task_id"] == "task_a"
    print("[OK] Released Task A (Budget verified: Remaining 100 tokens).")
    
    # --- 1st Execution completes ---
    # 1. Charges 150 tokens into the quota (draining into deficit!)
    res_manager.charge_resource(agent_drain, tokens=150, duration_ms=10)
    
    # 2. Satisfies the Causal Token by registering completion to Ledger!
    await event_engine.emit(SystemEvent(
        workflow_id=wf_depletion, action="EXEC_DONE", workflow_node_id="task_a_done"
    ))
    
    # 3. TRIGGER SOFT SUSPEND in hypervisor due to budget breach!
    await proc_drain.suspend_for_resources("TOKEN", usage_report="Balance hit -50 tokens")
    print(f"[WARNING] Depletion Intercepted! State shifted to: {proc_drain.pcb.state}")
    assert proc_drain.pcb.state == "RESOURCE_SUSPENDED"

    # 2nd Evaluation: Task B causal token IS met, but now it's BLOCKED by Depleted Resource!
    dispatched_2 = await scheduler.evaluate_and_dispatch()
    print(f"[DEBUG] Released on Eval 2: {[t['task_id'] for t in dispatched_2]}")
    assert len(dispatched_2) == 0
    print("[OK] Task B successfully BLOCKED and quarantined due to exhaustion.")

    # REPLENISHMENT & RECOVERY
    print("\n[SIM] Replenishing resource quotas (Reset balance to 500 tokens) and issuing Resume...")
    # Replenish budget
    res_manager.provision_quota(agent_drain, ResourceQuota(max_tokens=500, consumed_tokens=0))
    # Resume Process
    await proc_drain.resume()
    
    # 3rd Evaluation: Task B now releases seamlessly! Continuity preserved!
    dispatched_3 = await scheduler.evaluate_and_dispatch()
    print(f"[DEBUG] Released on Eval 3: {[t['task_id'] for t in dispatched_3]}")
    assert len(dispatched_3) == 1
    assert dispatched_3[0]["task_id"] == "task_b"
    print("[OK] Task B successfully released after recovery continuity loop!")
    print("[OK] Seamless uninterrupted process orchestration verified.\n")

    print("==================================================")
    print("    FASE 4 COMPLETE: COGNITIVE HYPERVISOR PASS!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_hypervisor_simulation())
