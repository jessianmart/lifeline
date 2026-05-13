from typing import List
from lifeline.core.events import EventBase
from lifeline.graph.lineage import OperationalLineageGraph
from lifeline.adapters.storage.base import AbstractEventStore

class CausalContextCollector:
    """
    Specialized context extractor that traverses the operational DAG.
    Identifies direct parent dependencies, branching forks, and divergent logic paths.
    """
    def __init__(self, store: AbstractEventStore):
        self.graph = OperationalLineageGraph(store)

    async def collect_causal_ancestry(self, latest_event_id: str, max_depth: int = 15) -> List[EventBase]:
        """
        Retrieves immediate linear and parallel ancestral node list.
        Restricts to a safe max_depth to contain prompt explosion.
        """
        full_ancestry = await self.graph.get_causal_ancestry(latest_event_id)
        # Limit depth from recent (end of array is newest due to BFS reversal)
        return full_ancestry[-max_depth:]

    async def identify_convergent_origin(self, event_a: str, event_b: str) -> str:
        """Retrieves the mutual root event where execution diverged into branches."""
        origin = await self.graph.find_convergent_ancestor(event_a, event_b)
        return origin or "GENESIS"
