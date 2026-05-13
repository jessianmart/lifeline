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
    def __init__(self, dlq_store: Optional[any] = None, fallback_log_path: str = "dead_letters_fallback.jsonl"):
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._catch_all_subscribers: List[EventHandler] = []
        self.dlq_store = dlq_store  # Injected AbstractEventStore for failed event recovery
        self.fallback_log_path = fallback_log_path

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
                        tb_str = "".join(traceback.format_exception(type(result), result, result.__traceback__))
                        try:
                            # Write directly to Secure Ledger Forensics Table
                            await self.dlq_store.store_dead_letter(
                                event_id=event.event_id,
                                subscriber_name=handler_name,
                                error_message=str(result),
                                stack_trace=tb_str,
                                event_payload=event.model_dump_json()
                            )
                        except Exception as dlq_fatal:
                            # JSONL Escape Hatch: Offload physical I/O asynchronously to prevent asyncio loop starvation
                            try:
                                import json
                                from datetime import datetime, timezone
                                fallback_record = {
                                    "event_id": event.event_id,
                                    "failed_at": datetime.now(timezone.utc).isoformat(),
                                    "subscriber_name": handler_name,
                                    "error_message": str(result),
                                    "stack_trace": tb_str,
                                    "dlq_fatal_cause": str(dlq_fatal),
                                    "event_payload": json.loads(event.model_dump_json())
                                }
                                
                                def sync_fallback_write(path, record):
                                    with open(path, "a", encoding="utf-8") as f_log:
                                        f_log.write(json.dumps(record) + "\n")
                                
                                # Safely execute blocking file I/O on native threadpool
                                await asyncio.to_thread(sync_fallback_write, self.fallback_log_path, fallback_record)
                                
                            except Exception as host_fatal:
                                # Absolute anti-recursive shield: Write to sys.stderr if local Host disk collapses entirely!
                                print(f"[CRITICAL SYSTEM FAULT] Dead Letter storage AND JSONL fallback failed: {host_fatal}", file=sys.stderr)
                    else:
                        # Fallback logging when no physical store is attached yet (boot sequence)
                        print(f"[Bus Critical] Missing DLQ sink. Event {event.event_id} processing crashed: {result}", file=sys.stderr)
