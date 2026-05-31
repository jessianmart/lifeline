from typing import List
from lifeline.core.events import EventBase
from lifeline.engines.event_engine import EventEngine

class TemporalContextCollector:
    """
    Captures continuous execution sequence ordered absolutely by Lamport logical clocks.
    Establishes baseline chronological awareness of recent actions.
    """
    def __init__(self, event_engine: EventEngine):
        self.engine = event_engine

    async def collect_recent_chain(self, workflow_id: str, count: int = 10) -> List[EventBase]:
        """
        Extracts the N most recent operations in this workflow chronologically.
        Leverages our fast-forward stream natively.
        """
        stream = self.engine.get_workflow_stream(workflow_id)
        all_events = []
        async for event in stream:
            all_events.append(event)
            
        # Return the last 'count' events to capture the active edge of progress
        return all_events[-count:]
