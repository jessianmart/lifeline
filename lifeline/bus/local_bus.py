import asyncio
from typing import Callable, Dict, List, Awaitable

from lifeline.core.events import EventBase
from lifeline.core.types import EventID

EventHandler = Callable[[EventBase], Awaitable[None]]

class LocalEventBus:
    """
    In-memory event bus for dispatching events to subscribers (engines, projections, memory).
    Crucial for decoupling Event Generation from Storage, Projections, and State Reconstruction.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._catch_all_subscribers: List[EventHandler] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribes a handler to a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribes a handler to all events."""
        self._catch_all_subscribers.append(handler)

    async def publish(self, event: EventBase) -> None:
        """Publishes an event to all relevant subscribers asynchronously."""
        event_type = getattr(event, "event_type", "base")
        handlers = self._subscribers.get(event_type, []) + self._catch_all_subscribers
        
        # Dispatch to all handlers concurrently
        if handlers:
            tasks = [handler(event) for handler in handlers]
            # Use return_exceptions=True so one failing handler doesn't crash the bus
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    # In a production system, this would go to a DLQ or Observability
                    # For now, we print or log it.
                    print(f"[Bus Error] Error handling event {event.event_id}: {result}")
