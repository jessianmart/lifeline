import asyncio
import sys
import traceback
from typing import Callable, Dict, List, Awaitable, Optional

from lifeline.core.events import EventBase
from lifeline.core.types import EventID

EventHandler = Callable[[EventBase], Awaitable[None]]

class LocalEventBus:
    """
    High-Resiliency in-memory event bus for dispatching events to subscribers.
    Decoupled from physical storage, leveraging secure Dead Letter Queues (DLQ)
    to preserve downstream auditability and prevent silent data loss.
    """
    def __init__(self, dlq_store: Optional[any] = None):
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._catch_all_subscribers: List[EventHandler] = []
        self.dlq_store = dlq_store  # Injected AbstractEventStore for failed event recovery

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
            # Use return_exceptions=True to isolate subscriber crashes
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    handler = handlers[idx]
                    handler_name = getattr(handler, "__name__", str(handler))
                    
                    # DLQ Injection Routing
                    if self.dlq_store:
                        try:
                            tb_str = "".join(traceback.format_exception(type(result), result, result.__traceback__))
                            
                            # Write directly to Secure Ledger Forensics Table
                            await self.dlq_store.store_dead_letter(
                                event_id=event.event_id,
                                subscriber_name=handler_name,
                                error_message=str(result),
                                stack_trace=tb_str,
                                event_payload=event.model_dump_json()
                            )
                        except Exception as dlq_fatal:
                            # Absolute anti-recursive shield: Write to sys.stderr if SQLite I/O breaks during DLQ insert
                            print(f"[FATAL DLQ ERROR] Deep corruption prevented DLQ commit: {dlq_fatal}", file=sys.stderr)
                    else:
                        # Fallback logging when no physical store is attached yet (boot sequence)
                        print(f"[Bus Critical] Missing DLQ sink. Event {event.event_id} processing crashed: {result}", file=sys.stderr)
