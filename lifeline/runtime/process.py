from typing import Literal, Dict, Any, Optional
from pydantic import BaseModel, Field
from lifeline.engines.event_engine import EventEngine
from lifeline.core.events import SystemEvent

# Expanded systems state list for high-res continuity governance
ProcessState = Literal[
    "SPAWNED", "RUNNING", "SUSPENDED", "RESOURCE_SUSPENDED",
    "SUSPENDED_RATE_LIMIT", "SLEEPING", "FAILED", "RECOVERING",
    "QUARANTINED", "REPLAYING", "TERMINATED"
]

class ProcessControlBlock(BaseModel):
    """Kernel metadata for a live Agent Process Thread."""
    pid: str
    agent_id: str
    workflow_id: str
    state: ProcessState = "SPAWNED"
    parent_pid: Optional[str] = None
    spawn_time: float = Field(default_factory=lambda: __import__('time').time())

class AgentProcess:
    """
    Cognitive Process Thread Controller.
    Manages operational state transitions, ensuring lifecycle events 
    are registered safely into the Causal Ledger for auditing.
    Supports interruptible cognition.
    """
    def __init__(self, pid: str, agent_id: str, workflow_id: str, event_engine: EventEngine):
        self.pcb = ProcessControlBlock(pid=pid, agent_id=agent_id, workflow_id=workflow_id)
        self.engine = event_engine

    async def spawn(self) -> str:
        """Registers creation of the thread into system memory."""
        self.pcb.state = "SPAWNED"
        return await self.engine.emit(SystemEvent(
            workflow_id=self.pcb.workflow_id,
            action="PROCESS_SPAWNED",
            payload={"pid": self.pcb.pid, "agent_id": self.pcb.agent_id}
        ))

    async def run(self) -> str:
        """Transitions execution into active computation."""
        self.pcb.state = "RUNNING"
        return await self.engine.emit(SystemEvent(
            workflow_id=self.pcb.workflow_id,
            action="PROCESS_RUN",
            payload={"pid": self.pcb.pid}
        ))

    async def suspend(self, reason: str = "voluntary") -> str:
        """Freezes execution logic, releasing active lock threads."""
        self.pcb.state = "SUSPENDED"
        return await self.engine.emit(SystemEvent(
            workflow_id=self.pcb.workflow_id,
            action="PROCESS_SUSPENDED",
            payload={"pid": self.pcb.pid, "reason": reason}
        ))

    async def suspend_for_resources(self, resource_type: str, usage_report: str) -> str:
        """Soft Suspend: Pauses execution due to quota exhaustion, preserving causality."""
        self.pcb.state = "RESOURCE_SUSPENDED"
        return await self.engine.emit(SystemEvent(
            workflow_id=self.pcb.workflow_id,
            action="PROCESS_RESOURCE_SUSPENDED",
            payload={
                "pid": self.pcb.pid, 
                "resource_type": resource_type,
                "report": usage_report
            }
        ))

    async def suspend_for_rate_limit(self, retry_after_sec: float) -> str:
        """Rate Limit Suspend: Pauses process due to API limits, recording expected wake barrier."""
        self.pcb.state = "SUSPENDED_RATE_LIMIT"
        return await self.engine.emit(SystemEvent(
            workflow_id=self.pcb.workflow_id,
            action="PROCESS_RATE_LIMITED",
            payload={
                "pid": self.pcb.pid,
                "retry_after_sec": retry_after_sec
            }
        ))

    async def quarantine(self, domain: str, reason: str) -> str:
        """Moves process into high-security quarantine isolate."""
        self.pcb.state = "QUARANTINED"
        return await self.engine.emit(SystemEvent(
            workflow_id=self.pcb.workflow_id,
            action="PROCESS_QUARANTINED",
            payload={"pid": self.pcb.pid, "domain": domain, "reason": reason}
        ))

    async def resume(self) -> str:
        """Restores process logic into active stream, resuming continuity."""
        self.pcb.state = "RUNNING"
        return await self.engine.emit(SystemEvent(
            workflow_id=self.pcb.workflow_id,
            action="PROCESS_RESUMED",
            payload={"pid": self.pcb.pid}
        ))

    async def terminate(self, code: int = 0) -> str:
        """Destroys the operational control block and releases final lock."""
        self.pcb.state = "TERMINATED"
        return await self.engine.emit(SystemEvent(
            workflow_id=self.pcb.workflow_id,
            action="PROCESS_TERMINATED",
            payload={"pid": self.pcb.pid, "exit_code": code}
        ))
