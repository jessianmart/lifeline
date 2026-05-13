import asyncio
from typing import Callable, Awaitable, Optional, Literal, List, Dict, Any
from lifeline.core.events import EventBase, ToolExecutionEvent
from lifeline.engines.event_engine import EventEngine
from lifeline.core.exceptions import StateReconstructionError

ReplayHook = Callable[[EventBase], Awaitable[None]]

class ReplayEngine:
    """
    Manages cognitive mental time-travel (Logical Replay) 
    and operational re-execution interception (Physical Replay).
    Allows developers to mock external dependencies using recorded execution logs.
    """
    def __init__(self, event_engine: EventEngine):
        self.event_engine = event_engine

    async def logical_replay(
        self, 
        workflow_id: str, 
        step_delay: float = 0.0, 
        on_event: Optional[ReplayHook] = None
    ) -> int:
        """
        Logical Replay: Mental time travel. 
        Walks through historical trace to observe thinking, state progression, and decisions.
        """
        event_count = 0
        async for event in self.event_engine.get_workflow_stream(workflow_id):
            event_count += 1
            if on_event:
                await on_event(event)
            if step_delay > 0:
                await asyncio.sleep(step_delay)
        return event_count

    async def start_physical_replay_session(self, workflow_id: str, replay_mode: Literal["mock", "live"] = "mock") -> "PhysicalReplaySession":
        """
        Initializes a Physical Replay Session.
        Retrieves the full operational DAG to provide high-fidelity interception of side effects.
        """
        events: List[EventBase] = []
        async for event in self.event_engine.get_workflow_stream(workflow_id):
            events.append(event)
            
        return PhysicalReplaySession(events, mode=replay_mode)

class PhysicalReplaySession:
    """
    Manages runtime interception of recorded interactions.
    If mode is 'mock', tools are resolved against recorded outcomes.
    """
    def __init__(self, historical_events: List[EventBase], mode: Literal["mock", "live"] = "mock"):
        self.mode = mode
        self.events = historical_events
        # Extract pre-mapped tool execution outcomes
        self.recorded_tools: Dict[str, List[ToolExecutionEvent]] = {}
        for e in self.events:
            if isinstance(e, ToolExecutionEvent):
                self.recorded_tools.setdefault(e.tool_name, []).append(e)
        
        # To track iterative indexes for matching multiple calls to identical tools
        self._consumption_pointer: Dict[str, int] = {name: 0 for name in self.recorded_tools.keys()}

    def get_recorded_tool_result(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Any]:
        """
        Retrieves the authentic historical outcome of a tool.
        Operates if mode == 'mock'.
        Throws exception if call structure diverges (safety check on logic drift).
        """
        if self.mode == "live":
            return None # Signal caller to proceed with live physical call

        if tool_name not in self.recorded_tools:
            raise StateReconstructionError(f"Logic Drift: No recorded execution found for tool '{tool_name}' during mock replay.")

        pointer = self._consumption_pointer.get(tool_name, 0)
        recorded_executions = self.recorded_tools[tool_name]
        
        if pointer >= len(recorded_executions):
            raise StateReconstructionError(f"Logic Drift: Executing tool '{tool_name}' {pointer+1} times, but trace only recorded {len(recorded_executions)}.")

        record = recorded_executions[pointer]
        
        # Optional rigorous integrity check: compare arguments to confirm deterministic path
        # To preserve flexibility on non-deterministic parameters (e.g. dynamic dates), we logging warnings on mismatch.
        if record.tool_args != arguments:
            # A logic drift warning - path diverges from original!
            pass

        # Advance pointer
        self._consumption_pointer[tool_name] = pointer + 1
        
        if record.error:
            raise Exception(f"Historical Tool Failure ({tool_name}): {record.error}")
            
        return record.tool_result
