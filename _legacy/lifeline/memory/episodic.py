from typing import List
from lifeline.core.events import EventBase
from lifeline.engines.event_engine import EventEngine

class EpisodicMemory:
    """Tier 2: Immutable serial trace of historical ledger actions."""
    def __init__(self, event_engine: EventEngine):
        self.engine = event_engine

    async def recall_episodes(self, workflow_id: str) -> List[EventBase]:
        """
        Recalls chronological events from the ledger for the specified workflow.
        """
        episodes = []
        async for ev in self.engine.get_workflow_stream(workflow_id):
            episodes.append(ev)
        return episodes
