import asyncio
import time
from typing import Dict, Any, List
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
    The Concurrent Application Supervisor.
    Fires parallel scheduler tasks non-blockingly, inducing massive ledger storm pressure.
    """
    def __init__(self, db_file: str, unsafe_allow_host_execution: bool = False):
        from lifeline.adapters.storage.sqlite import SQLiteEventStore
        self.store = SQLiteEventStore(db_file)
        
        self.res_manager = ResourceManager()
        self.sandbox = IsolatedSandboxExecutor(self.res_manager, unsafe_allow_host_execution=unsafe_allow_host_execution)
        self.policy_engine = PolicyEngine()

    async def bootstrap(self):
        await self.store.initialize()
        self.event_engine = EventEngine(self.store)
        self.state_engine = StateEngine(self.event_engine, None)
        self.ctx_engine = ContextEngine(self.store, self.event_engine, self.state_engine)
        self.scheduler = CognitiveScheduler(
            self.event_engine, self.ctx_engine, self.policy_engine, resource_manager=self.res_manager
        )

    async def run_chaos_storm(self, workflow_id: str, fix_perm_content: str, branch_count: int = 3):
        """Drives concurrent multi-agent parallel thread satuation."""
        print("\n==================================================")
        print(f"   LAUNCHING CAUSAL STORM (Branches = {branch_count})")
        print("==================================================\n")
        
        # Step 1: Provision quotas & load PCB pools for dynamic agent swarm
        coders = {}
        testers = {}
        
        planner = PlannerAgent(pid="PID_PLAN_00", agent_id="planner_v1", workflow_id=workflow_id, event_engine=self.event_engine)
        await planner.initialize()
        
        for i in range(1, branch_count + 1):
            c_id = f"coder_bot_0{i}"
            t_id = f"tester_bot_0{i}"
            # Provision 2000 tokens each to support parallel physical runs
            self.res_manager.provision_quota(c_id, ResourceQuota(max_tokens=2000, max_execution_ms=30000))
            self.res_manager.provision_quota(t_id, ResourceQuota(max_tokens=2000, max_execution_ms=30000))
            
            coder = CoderAgent(pid=f"PID_CODE_0{i}", agent_id=c_id, workflow_id=workflow_id, event_engine=self.event_engine)
            tester = TesterAgent(pid=f"PID_TEST_0{i}", agent_id=t_id, workflow_id=workflow_id, event_engine=self.event_engine, sandbox_executor=self.sandbox)
            
            await coder.initialize()
            await tester.initialize()
            
            coders[c_id] = coder
            testers[t_id] = tester

        print("[SYSTEM] Parallel Agent Block Pools Spawned and Bound.")

        # Step 2: Planner ingests issue and splits DAG into 6 independent tasks (3 coders, 3 testers)
        tasks = await planner.plan_chaos_resolution("Massive assert failure", branch_count=branch_count)
        for t in tasks:
            self.scheduler.submit_task(t)

        latest = await self.store.get_latest_workflow_event(workflow_id)
        root_id = latest.event_id if latest else ""

        loop_active = True
        cycle_count = 0
        success_branches = []

        t_start_storm = time.perf_counter()

        # Non-blocking dispatch attention loop
        try:
            while loop_active and cycle_count < 5:
                cycle_count += 1
                print(f"\n--- [CYCLE {cycle_count}] Multi-Thread Dispatch Scan ---")
                
                dispatches = await self.scheduler.evaluate_and_dispatch()
                print(f"[SCHEDULER] Released {len(dispatches)} Tasks concurrently!")
                
                if not dispatches and not self.scheduler._backlog:
                    print("[SYSTEM] No remaining tasks. Causal storm subsided.")
                    break

                # Hardening: Parallel coroutine launching via asyncio.gather!
                active_coroutines = []

                for dispatch in dispatches:
                    action = dispatch["action"]
                    agent_id = dispatch["agent_id"]
                    payload = dispatch["payload"]
                    
                    branch_id = payload["branch_id"]
                    
                    # Route correctly based on concurrent task groups
                    if action.startswith("CODE_PATCH"):
                        coder_inst = coders[agent_id]
                        file_path = payload["file_to_fix"]
                        
                        # Add to parallel batch
                        active_coroutines.append(
                            coder_inst.write_patch(file_path, fix_perm_content, branch_id, parent_event_id=root_id)
                        )
                        
                    elif action.startswith("RUN_TESTS"):
                        tester_inst = testers[agent_id]
                        test_cmd = payload["test_command"]
                        
                        # Helper routine to capture parallel outputs
                        async def run_tester_flow(t_inst, cmd, b_id):
                            ok = await t_inst.execute_test(cmd, b_id)
                            if ok:
                                success_branches.append(b_id)
                                
                        active_coroutines.append(run_tester_flow(tester_inst, test_cmd, branch_id))

                # EXECUTE BATCH SIMULTANEOUSLY IN PARALLEL
                if active_coroutines:
                    print(f"[SYSTEM] Firing {len(active_coroutines)} parallel Sandbox threads now...")
                    await asyncio.gather(*active_coroutines)
                    print(f"[SYSTEM] Batch parallel join completed successfully.")

                await asyncio.sleep(0.2)
        finally:
            # Cleanup all processes
            await planner.process.terminate()
            for c in coders.values(): await c.process.terminate()
            for t in testers.values(): await t.process.terminate()

        t_end_storm = time.perf_counter()
        total_storm_time = t_end_storm - t_start_storm

        # Print physical storm statistics
        print("\n==================================================")
        print("        CAUSAL STORM RUNTIME STATISTICS")
        print("==================================================")
        print(f"Total Concurrency Wall-Time: {total_storm_time*1000:.2f}ms")
        print(f"Successful Self-Repaired Branches: {success_branches}")
        
        # Query SQLite events total
        events_count = 0
        async for _ in self.store.get_workflow_stream(workflow_id):
            events_count += 1
            
        print(f"Ledger Events Flooded: {events_count} total")
        print(f"Ingestion Throughput: {events_count / total_storm_time:.2f} events/sec")
        print("==================================================\n")

        return len(success_branches) == branch_count
