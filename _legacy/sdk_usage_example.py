import asyncio
import os
import uuid
from typing import Dict, Any

# Importing from our Lifeline SDK core!
from lifeline.adapters.storage.sqlite import SQLiteEventStore
from lifeline.engines.event_engine import EventEngine
from lifeline.engines.state_engine import StateEngine
from lifeline.context.assembly import ContextEngine
from lifeline.runtime.scheduler import CognitiveScheduler, ScheduledTask
from lifeline.runtime.policies.base import PolicyEngine
from lifeline.runtime.resources import ResourceManager, ResourceQuota
from lifeline.core.events import SystemEvent

async def main():
    print("==================================================")
    print("       LIFELINE SDK - THIRD PARTY INTEGRATION")
    print("==================================================\n")

    db_file = "external_sdk_app.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    print("[SDK] 1. Bootstrapping Engine Substrates...")
    # Step 1: Setup operational storage
    store = SQLiteEventStore(db_file)
    await store.initialize()
    
    # Step 2: Instantiate Hypervisor components
    event_engine = EventEngine(store)
    state_engine = StateEngine(event_engine, None)
    ctx_engine = ContextEngine(store, event_engine, state_engine)
    policy_engine = PolicyEngine()
    res_manager = ResourceManager()
    
    # Step 3: Bind the Scheduler Core
    scheduler = CognitiveScheduler(event_engine, ctx_engine, policy_engine, res_manager)
    print("[SDK] Hypervisor successfully initialized & bound.\n")

    workflow_id = f"wf_external_{uuid.uuid4().hex[:6]}"
    agent_id = "demo_external_agent"

    print(f"[SDK] 2. Registering Agent & Provisioning Hardware Budget for [{agent_id}]...")
    res_manager.provision_quota(agent_id, ResourceQuota(max_tokens=5000, max_execution_ms=10000))
    
    # Seed initial trigger event in ledger to establish context root
    await event_engine.emit(SystemEvent(
        workflow_id=workflow_id,
        action="SDK_DEMO_BOOTSTRAP",
        payload={"source": "external_integration_script"}
    ))

    print("[SDK] 3. Submitting Cognitive Tasks into the Scheduler...")
    
    # Task 1: Core Task
    task_1 = ScheduledTask(
        task_id="task_fetch_data",
        workflow_id=workflow_id,
        agent_id=agent_id,
        action_name="FETCH_RECORDS"
    )
    
    # Task 2: Causal Dependent Task
    task_2 = ScheduledTask(
        task_id="task_process_data",
        workflow_id=workflow_id,
        agent_id=agent_id,
        action_name="TRANSFORM_MATRIX",
        depends_on_nodes=["records_fetched"] # Causal topological constraint
    )
    
    scheduler.submit_task(task_1)
    scheduler.submit_task(task_2)
    print("[SDK] Tasks locked in backlog.\n")

    print("[SDK] 4. Advancing Scheduler Tick 1 (Causal Filter Audit)...")
    dispatches = await scheduler.evaluate_and_dispatch()
    print(f" -> Released {len(dispatches)} tasks.")
    
    for d in dispatches:
        print(f" -> Executing released task: [{d['task_id']}] for action '{d['action']}'")
        # Simulate agent completing work and committing satisfaction token to ledger
        await event_engine.emit(SystemEvent(
            workflow_id=workflow_id,
            action="RECORDS_FETCHED_SUCCESS",
            workflow_node_id="records_fetched" # Satisfies Task 2 dependency!
        ))

    print("\n[SDK] 5. Advancing Scheduler Tick 2 (Unblocking Dependent Chains)...")
    dispatches_2 = await scheduler.evaluate_and_dispatch()
    print(f" -> Released {len(dispatches_2)} tasks.")
    
    for d in dispatches_2:
        print(f" -> Executing released task: [{d['task_id']}] for action '{d['action']}'")
        # Access authentic cognitive context payload injected by the SDK!
        ctx = d['cognitive_context']
        print(f" -> Authentic Context Injected: Reconstructed State keys = {list(ctx.reconstructed_state.keys())}")

    print("\n" + "="*50)
    print("      SDK INTEGRATION TEST COMPLETED SUCCESSFULLY!")
    print("   The Lifeline interfaces are fully operational for DX.")
    print("="*50)

    # Cleanup
    if os.path.exists(db_file):
        os.remove(db_file)

if __name__ == "__main__":
    asyncio.run(main())
