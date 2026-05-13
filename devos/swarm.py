import asyncio
import time
from typing import Dict, Any
from lifeline.engines.event_engine import EventEngine
from lifeline.engines.state_engine import StateEngine
from lifeline.context.assembly import ContextEngine
from lifeline.runtime.scheduler import CognitiveScheduler
from lifeline.runtime.policies.base import PolicyEngine
from lifeline.runtime.resources import ResourceManager, ResourceQuota
from lifeline.runtime.sandbox import IsolatedSandboxExecutor
from .agents import PlannerAgent, CoderAgent, TesterAgent

class DevOSSwarmOrchestrator:
    """
    The Application Supervisor.
    Drives the lifecycle loop of Specialized Developer Agents using the underlying Hypervisor.
    """
    def __init__(self, db_file: str):
        from lifeline.adapters.storage.sqlite import SQLiteEventStore
        self.store = SQLiteEventStore(db_file)
        
        self.res_manager = ResourceManager()
        self.sandbox = IsolatedSandboxExecutor(self.res_manager)
        self.policy_engine = PolicyEngine()

    async def bootstrap(self):
        await self.store.initialize()
        self.event_engine = EventEngine(self.store)
        self.state_engine = StateEngine(self.event_engine, None)
        self.ctx_engine = ContextEngine(self.store, self.event_engine, self.state_engine)
        self.scheduler = CognitiveScheduler(
            self.event_engine, self.ctx_engine, self.policy_engine, resource_manager=self.res_manager
        )

    async def run_stress_loop(self, workflow_id: str, broken_file: str, patch_content: str, test_cmd: list[str]):
        """Coordinates the continuous autonomous coding loop."""
        print("\n==================================================")
        print("     BOOTSTRAPPING DEVOS SWARM SUPERVISOR")
        print("==================================================")
        
        # Provision hardware budget: 2000 tokens, 30s execution limits
        self.res_manager.provision_quota("coder_bot_01", ResourceQuota(max_tokens=2000, max_execution_ms=30000))
        self.res_manager.provision_quota("tester_bot_01", ResourceQuota(max_tokens=2000, max_execution_ms=30000))
        
        # Instantiate active agents
        planner = PlannerAgent(pid="PID_PLAN_01", agent_id="planner_v1", workflow_id=workflow_id, event_engine=self.event_engine)
        coder = CoderAgent(pid="PID_CODE_02", agent_id="coder_bot_01", workflow_id=workflow_id, event_engine=self.event_engine)
        tester = TesterAgent(pid="PID_TEST_03", agent_id="tester_bot_01", workflow_id=workflow_id, event_engine=self.event_engine, sandbox_executor=self.sandbox)
        
        await planner.initialize()
        await coder.initialize()
        await tester.initialize()

        print("[SYSTEM] Sub-Agent Control Blocks initialized and loaded.\n")

        # Step 1: Issue Ingestion
        tasks = await planner.plan_resolution(f"Assert failure detected in local tests.")
        for t in tasks:
            self.scheduler.submit_task(t)

        # Get root event for DAG linking
        latest = await self.store.get_latest_workflow_event(workflow_id)
        root_id = latest.event_id if latest else ""

        loop_active = True
        cycle_count = 0
        tests_passed = False

        # Continuous attention attention loop!
        while loop_active and cycle_count < 5:
            cycle_count += 1
            print(f"--- [CYCLE {cycle_count}] Triggering Scheduler Dispatch Engine ---")
            
            # Verify who is eligible
            dispatches = await self.scheduler.evaluate_and_dispatch()
            print(f"[SCHEDULER] Released {len(dispatches)} Tasks.")
            
            if not dispatches and not self.scheduler._backlog:
                print("[SYSTEM] No remaining tasks in scheduler. Exiting loop.")
                break

            for dispatch in dispatches:
                action = dispatch["action"]
                task_id = dispatch["task_id"]
                
                print(f"[SYSTEM] Launching thread '{task_id}' for action '{action}'...")
                
                if action == "CODE_PATCH":
                    # Coder Agent writes patch
                    await coder.write_patch(broken_file, patch_content, parent_event_id=root_id)
                    
                elif action == "RUN_TESTS":
                    # Tester Agent runs actual subprocess tests in local Sandbox
                    success = await tester.execute_test(test_cmd)
                    if success:
                        print("\n[VICTORY] Swarm completed work. Causal Test validation SUCCEEDED!")
                        tests_passed = True
                        loop_active = False
                    else:
                        print("\n[FAIL] Causal Test validation FAILED inside the Sandbox.")
                        loop_active = False

            # Breathe loop
            await asyncio.sleep(0.5)

        # Terminate Process Contexts
        await planner.process.terminate()
        await coder.process.terminate()
        await tester.process.terminate()
        
        print("\n[SYSTEM] Swarm terminated. Releasing allocated Hardware Resources.")
        return tests_passed
