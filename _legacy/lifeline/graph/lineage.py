from typing import List, Set, Dict, Optional
from collections import deque

from lifeline.adapters.storage.base import AbstractEventStore
from lifeline.core.events import EventBase
from lifeline.core.types import EventID

class OperationalLineageGraph:
    """
    Provides graph-native algorithms and traversal operations 
    for interpreting the operational DAG ledger.
    Allows advanced debugging, branch tracking, and retry ancestry analysis.
    """
    def __init__(self, store: AbstractEventStore):
        self.store = store

    async def get_causal_ancestry(self, start_event_id: EventID) -> List[EventBase]:
        """
        Performs a reverse breadth-first search (BFS) to retrieve the 
        entire historical ancestry tree for an event.
        """
        visited: Set[str] = set()
        ancestry: List[EventBase] = []
        queue = deque([start_event_id])

        while queue:
            current_id = queue.popleft()
            if current_id in visited:
                continue
            
            event = await self.store.get_event(current_id)
            if not event:
                continue

            visited.add(current_id)
            ancestry.append(event)

            # Fetch graph-linked parents
            parents = await self.store.get_parent_events(current_id)
            for p in parents:
                if p.event_id not in visited:
                    queue.append(p.event_id)
                    
        # Return reversed so it mimics forward flow representation (oldest first)
        ancestry.reverse()
        return ancestry

    async def get_descendant_impact_tree(self, start_event_id: EventID) -> List[EventBase]:
        """
        Retrieves every node that was triggered OR directly affected 
        downstream by this event (Cascading Impact Analysis).
        """
        visited: Set[str] = set()
        descendants: List[EventBase] = []
        queue = deque([start_event_id])

        while queue:
            current_id = queue.popleft()
            if current_id in visited:
                continue
            
            event = await self.store.get_event(current_id)
            if not event:
                continue

            visited.add(current_id)
            if current_id != start_event_id:
                descendants.append(event)

            children = await self.store.get_child_events(current_id)
            for c in children:
                if c.event_id not in visited:
                    queue.append(c.event_id)

        return descendants

    async def find_convergent_ancestor(self, event_a_id: EventID, event_b_id: EventID) -> Optional[EventID]:
        """
        Identifies the closest shared historical node prior to a fork or branching divergence.
        """
        # Traverse and cache all ancestors for event A
        visited_a = set()
        queue_a = deque([event_a_id])
        while queue_a:
            curr = queue_a.popleft()
            if curr not in visited_a:
                visited_a.add(curr)
                parents = await self.store.get_parent_events(curr)
                queue_a.extend([p.event_id for p in parents])

        # Traverse ancestors for event B and return the first intersection
        queue_b = deque([event_b_id])
        visited_b = set()
        while queue_b:
            curr = queue_b.popleft()
            if curr in visited_a:
                return curr # Immediate common origin found
            if curr not in visited_b:
                visited_b.add(curr)
                parents = await self.store.get_parent_events(curr)
                queue_b.extend([p.event_id for p in parents])

        return None
