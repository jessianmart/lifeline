import time
import os
from typing import Dict, Any, List, Optional
from lifeline.runtime.process import AgentProcess
from lifeline.core.events import SystemEvent, ToolExecutionEvent
from lifeline.runtime.scheduler import ScheduledTask

class DevOSAgentBase:
    """Wrapper combining Logical Agent Intelligence with Systems Process Control Blocks."""
    def __init__(self, pid: str, agent_id: str, workflow_id: str, event_engine: Any):
        self.process = AgentProcess(pid=pid, agent_id=agent_id, workflow_id=workflow_id, event_engine=event_engine)
        self.event_engine = event_engine

    async def initialize(self):
        await self.process.spawn()
        await self.process.run()

class PlannerAgent(DevOSAgentBase):
    """Deconstructs engineering tickets into massive concurrent Task DAGs."""
    async def plan_resolution(self, issue_desc: str) -> List[ScheduledTask]:
        # Legacy Single-Agent Plan for backwards compatibility
        return await self.plan_chaos_resolution(issue_desc, branch_count=1)

    async def plan_chaos_resolution(self, issue_desc: str, branch_count: int = 3) -> List[ScheduledTask]:
        print(f"[{self.process.pcb.pid} - PLANNER] Initializing CAOS BRANCH PLAN for {branch_count} branches...")
        
        await self.event_engine.emit(SystemEvent(
            workflow_id=self.process.pcb.workflow_id,
            action="CHAOS_PLAN_CREATED",
            payload={"issue": issue_desc, "branches": branch_count}
        ))

        tasks = []
        for idx in range(1, branch_count + 1):
            suffix = chr(64 + idx) # A, B, C...
            
            # 1. Coder Task
            t_coder = ScheduledTask(
                task_id=f"task_generate_fix_{suffix}",
                workflow_id=self.process.pcb.workflow_id,
                agent_id=f"coder_bot_0{idx}",
                action_name=f"CODE_PATCH_{suffix}",
                payload={
                    "file_to_fix": f"broken_module_{suffix}.py",
                    "branch_id": suffix
                }
            )
            
            # 2. Tester Task - Causal Blocked on its Coder sibling token!
            t_tester = ScheduledTask(
                task_id=f"task_run_tests_{suffix}",
                workflow_id=self.process.pcb.workflow_id,
                agent_id=f"tester_bot_0{idx}",
                action_name=f"RUN_TESTS_{suffix}",
                payload={
                    "test_command": ["python", "-m", "unittest", f"test_broken_{suffix}.py"],
                    "branch_id": suffix
                },
                depends_on_nodes=[f"patch_written_{suffix}"] # Distinct causal barrier
            )
            
            tasks.append(t_coder)
            tasks.append(t_tester)

        return tasks

class CoderAgent(DevOSAgentBase):
    """Consumes context state and writes code permutations onto diverging branches."""
    async def write_patch(self, file_path: str, patch_content: str, branch_id: str, parent_event_id: str) -> str:
        print(f"[{self.process.pcb.pid} - CODER] Generating Permutation '{branch_id}' for '{file_path}'...")
        
        # Write isolated physical codebase permutation
        with open(file_path, "w") as f:
            f.write(patch_content)

        # Emit patch emission coupled to specific branch token!
        return await self.event_engine.emit(ToolExecutionEvent(
            workflow_id=self.process.pcb.workflow_id,
            tool_name="write_patch_file",
            tool_args={"file": file_path, "branch": branch_id},
            parent_event_ids=[parent_event_id],
            workflow_node_id=f"patch_written_{branch_id}" # Unlocks specific sibling!
        ))

class TesterAgent(DevOSAgentBase):
    """Spawns physical host subprocess isolates auditing tests outcomes."""
    def __init__(self, pid: str, agent_id: str, workflow_id: str, event_engine: Any, sandbox_executor: Any):
        super().__init__(pid, agent_id, workflow_id, event_engine)
        self.sandbox = sandbox_executor

    async def execute_test(self, test_cmd: List[str], branch_id: str) -> bool:
        print(f"[{self.process.pcb.pid} - TESTER] Spawning Sandboxed Isolator for Branch '{branch_id}'...")
        
        # 1. Execute concurrent physical process
        result, telemetry = await self.sandbox.execute_physical_command(
            agent_id=self.process.pcb.agent_id,
            cmd_args=test_cmd
        )
        
        success = telemetry.success
        print(f" -> [OUTCOME '{branch_id}'] Success={success} | CPU Time={telemetry.execution_time_ms}ms | ExitCode={result['returncode']}")
        
        # 2. Record to shared Causal Ledger
        await self.event_engine.emit(SystemEvent(
            workflow_id=self.process.pcb.workflow_id,
            action="TEST_SUITE_EXECUTED",
            workflow_node_id=f"tests_completed_{branch_id}",
            payload={
                "branch": branch_id,
                "success": success,
                "exit_code": result["returncode"],
                "duration_ms": telemetry.execution_time_ms,
                "tokens_consumed": telemetry.tokens_consumed
            }
        ))

        return success
