import asyncio
from typing import Optional

from lifeline.bus.local_bus import LocalEventBus
from lifeline.core.events import EventBase, SystemEvent
from lifeline.engines.event_engine import EventEngine
from lifeline.engines.state_engine import StateEngine
from lifeline.engines.snapshot_engine import SnapshotEngine


class LifelineClient:
    """
    Main SDK Client.
    Initializes the cognitive microkernel components and wires them together.
    """

    def __init__(
        self,
        event_engine: EventEngine,
        state_engine: StateEngine,
        snapshot_engine: SnapshotEngine,
        bus: LocalEventBus
    ):
        self.event_engine = event_engine
        self.state_engine = state_engine
        self.snapshot_engine = snapshot_engine
        self.bus = bus
        
        # Wire the event engine to the bus so every published event gets stored
        self.bus.subscribe_all(self._persist_event)

    async def _persist_event(self, event: EventBase) -> None:
        """Internal handler to persist events flowing through the bus."""
        await self.event_engine.emit(event)

    async def publish(self, event: EventBase) -> None:
        """Publishes an event to the bus."""
        await self.bus.publish(event)

    async def start(self) -> None:
        """Starts the client and issues a system startup event."""
        start_event = SystemEvent(action="kernel_started")
        await self.publish(start_event)

    async def get_workflow_state(self, workflow_id: str) -> dict:
        """Reconstructs the current state of a workflow."""
        return await self.state_engine.rebuild_workflow_state(workflow_id)
