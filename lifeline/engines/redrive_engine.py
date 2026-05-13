import asyncio
from typing import List, Dict, Any

from lifeline.adapters.storage.base import AbstractEventStore
from lifeline.bus.local_bus import LocalEventBus
from lifeline.core.events import parse_event_from_json

class RedriveEngine:
    """
    The Fault Reclamation Controller.
    Orchestrates the recovery cycle of unprocessed event payloads trapped in the DLQ,
    injecting concurrency safeguards and leveraging the physical ledger's selective idempotency guarantees.
    """
    def __init__(self, store: AbstractEventStore, bus: LocalEventBus):
        self.store = store
        self.bus = bus
        self._in_flight_records = set()  # In-memory processing lock against duplicate races

    async def list_dead_letters(self) -> List[dict]:
        """Retrieves snapshot of all failing events pending manual or automated intervention."""
        return await self.store.get_dead_letters()

    async def redrive_event(self, record_id: int) -> bool:
        """
        Attempts programmatic re-emission of a dead letter back into the causal stream.
        Uses in-memory transient locks and physical cleanup to prevent duplicate processing storms.
        """
        if record_id in self._in_flight_records:
            # Lock acquisition failure: record is already actively being processed by another thread
            return False
            
        self._in_flight_records.add(record_id)
        try:
            # 1. Fetch specific target record
            records = await self.store.get_dead_letters()
            target = next((r for r in records if r["id"] == record_id), None)
            
            if not target:
                return False
                
            # 2. Re-inflate raw event structure preserving original causal ID and Lamport links
            event = parse_event_from_json(target["event_payload"])
            
            # 3. Inject directly back into the Event Bus
            # Underneath, the SQLite storage subscription will utilize Selective Idempotency
            # to silently pass duplicate insertions, while downstream workers attempt execution again.
            await self.bus.publish(event)
            
            # 4. Safe Post-Action Purge: If re-processing raised a new error,
            # the Bus has already registered a FRESH record with a NEW record_id.
            # We can safely eliminate this resolved/expired DLQ tombstone.
            await self.store.delete_dead_letter(record_id)
            return True
            
        except Exception:
            # Bubble failure upwards while ensuring the lock gets released cleanly
            raise
        finally:
            self._in_flight_records.discard(record_id)

    async def redrive_all(self) -> int:
        """Bulk-processes all pending dead letters in chronological sequence of failure."""
        letters = await self.list_dead_letters()
        success_count = 0
        for letter in letters:
            ok = await self.redrive_event(letter["id"])
            if ok:
                success_count += 1
        return success_count
