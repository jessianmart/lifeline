from typing import Dict, Any
from lifeline.engines.state_engine import StateEngine

class OperationalMemory:
    """Tier 3: Current consolidated system memory and fast recovery state."""
    def __init__(self, state_engine: StateEngine):
        self.engine = state_engine

    async def recall_operational_state(self, workflow_id: str) -> Dict[str, Any]:
        """
        Recalls the current consolidated state projection of the workflow.
        """
        return await self.engine.rebuild_workflow_state(workflow_id)
