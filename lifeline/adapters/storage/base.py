from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional

from lifeline.core.events import EventBase
from lifeline.core.types import EventID, WorkflowID, AgentID


class AbstractEventStore(ABC):
    """
    Abstract base class for Event Storage.
    The store must be append-only and preserve causal ordering.
    """

    @abstractmethod
    async def append(self, event: EventBase) -> None:
        """Appends a new event to the store."""
        pass

    @abstractmethod
    async def append_batch(self, events: List[EventBase]) -> None:
        """Appends a batch of events atomically."""
        pass

    @abstractmethod
    async def get_event(self, event_id: EventID) -> Optional[EventBase]:
        """Retrieves a single event by its ID."""
        pass

    @abstractmethod
    def get_workflow_stream(self, workflow_id: WorkflowID, since_logical_clock: int = -1) -> AsyncIterator[EventBase]:
        """Retrieves all events for a given workflow in causal order."""
        pass

    @abstractmethod
    def get_agent_stream(self, agent_id: AgentID, since_logical_clock: int = -1) -> AsyncIterator[EventBase]:
        """Retrieves all events for a given agent in causal order."""
        pass

    @abstractmethod
    async def get_latest_workflow_event(self, workflow_id: WorkflowID) -> Optional[EventBase]:
        """Retrieves the most recent event in the workflow chain."""
        pass

    @abstractmethod
    async def get_latest_agent_event(self, agent_id: AgentID) -> Optional[EventBase]:
        """Retrieves the most recent event in the agent chain."""
        pass

    @abstractmethod
    async def get_parent_events(self, child_id: EventID) -> List[EventBase]:
        """Fetches immediate causal parents of an event."""
        pass

    @abstractmethod
    async def get_child_events(self, parent_id: EventID) -> List[EventBase]:
        """Fetches immediate causal children of an event."""
        pass

    @abstractmethod
    async def store_dead_letter(self, event_id: str, subscriber_name: str, error_message: str, stack_trace: str, event_payload: str) -> None:
        """Persists a failed event processing to the Dead Letter Queue."""
        pass


class AbstractSnapshotStore(ABC):
    """
    Abstract base class for Snapshot Storage.
    """

    @abstractmethod
    async def save_snapshot(self, entity_id: str, state: dict, last_event_id: EventID, snapshot_type: str = "state") -> None:
        """Saves a checkpoint of an entity's state at a specific event."""
        pass

    @abstractmethod
    async def get_latest_snapshot(self, entity_id: str) -> Optional[dict]:
        """Retrieves the most recent snapshot for an entity."""
        pass
