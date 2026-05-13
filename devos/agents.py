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
    """Deconstructs engineering tickets into causal Task DAGs."""
    async def plan_resolution(self, issue_desc: str) -> List[ScheduledTask]:
        print(f"[{self.process.pcb.pid} - PLANNER] Ingesting Issue: '{issue_desc}'")
        
        # Register Plan inside Ledger
        await self.event_engine.emit(SystemEvent(
            workflow_id=self.process.pcb.workflow_id,
            action="PLAN_CREATED",
            payload={"issue": issue_desc}
        ))

        # Construct causal-linked Task objects
        # 1. Coder Agent: Generates corrections
        task_code = ScheduledTask(
            task_id="task_generate_fix",
            workflow_id=self.process.pcb.workflow_id,
            agent_id="coder_bot_01",
            action_name="CODE_PATCH",
            payload={"file_to_fix": "broken_module.py"}
        )

        # 2. Tester Agent: Blocked by Code completion node!
        task_test = ScheduledTask(
            task_id="task_run_tests",
            workflow_id=self.process.pcb.workflow_id,
            agent_id="tester_bot_01",
            action_name="RUN_TESTS",
            payload={"test_command": ["pytest", "test_broken.py"]},
            depends_on_nodes=["patch_written"] # Causal constraint!
        )

        return [task_code, task_test]

class CoderAgent(DevOSAgentBase):
    """Consumes context state and writes code permutations onto diverging branches."""
    async def write_patch(self, file_path: str, patch_content: str, parent_event_id: str) -> str:
        print(f"[{self.process.pcb.pid} - CODER] Generating Patch for '{file_path}'...")
        
        # Physically write file to disk simulation!
        with open(file_path, "w") as f:
            f.write(patch_content)

        # Emit patch emission coupled to DAG ancestry
        return await self.event_engine.emit(ToolExecutionEvent(
            workflow_id=self.process.pcb.workflow_id,
            tool_name="write_patch_file",
            tool_args={"file": file_path, "status": "success"},
            parent_event_ids=[parent_event_id],
            workflow_node_id="patch_written" # Satisfies Causal Blocker!
        ))

class TesterAgent(DevOSAgentBase):
    """Spawns physical host subprocess isolates auditing tests outcomes."""
    def __init__(self, pid: str, agent_id: str, workflow_id: str, event_engine: Any, sandbox_executor: Any):
        super().__init__(pid, agent_id, workflow_id, event_engine)
        self.sandbox = sandbox_executor

    async def execute_test(self, test_cmd: List[str]) -> bool:
        print(f"[{self.process.pcb.pid} - TESTER] Spawning Sandboxed Test Isolator: {' '.join(test_cmd)}...")
        
        # 1. Execute physical process on local machine!
        result, telemetry = await self.sandbox.execute_physical_command(
            agent_id=self.process.pcb.agent_id,
            cmd_args=test_cmd
        )
        
        success = telemetry.success
        print(f" -> [TEST OUTCOME] Success={success} | Duration={telemetry.execution_time_ms}ms | ExitCode={result['returncode']}")
        
        # 2. Emit test results into absolute ledger trace
        await self.event_engine.emit(SystemEvent(
            workflow_id=self.process.pcb.workflow_id,
            action="TEST_SUITE_EXECUTED",
            workflow_node_id="tests_completed",
            payload={
                "success": success,
                "exit_code": result["returncode"],
                "duration_ms": telemetry.execution_time_ms,
                "tokens_consumed": telemetry.tokens_consumed,
                "stdout_sample": result["stdout"][-100:] if result["stdout"] else ""
            }
        ))

        return success
