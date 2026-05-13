import json
import zlib
from typing import Optional, Dict, Any

from lifeline.adapters.storage.base import AbstractSnapshotStore
from lifeline.core.types import EventID
from lifeline.engines.state_engine import StateEngine
from lifeline.engines.event_engine import EventEngine
from lifeline.core.events import parse_event_from_json

class SnapshotEngine:
    """
    Manages taking, retrieving, and exporting checkpoints of state to optimize multi-node rebuilding.
    """

    def __init__(self, store: AbstractSnapshotStore, state_engine: StateEngine, event_engine: EventEngine):
        self.store = store
        self.state_engine = state_engine
        self.event_engine = event_engine

    async def create_snapshot(self, entity_id: str, current_state: Dict[str, Any], last_event_id: EventID, snapshot_type: str = "state") -> None:
        """
        Saves the current state as a robustly dimensioned snapshot (state, workflow, memory, context).
        """
        await self.store.save_snapshot(entity_id, current_state, last_event_id, snapshot_type=snapshot_type)

    async def get_latest_snapshot(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the latest snapshot metadata & state for an entity.
        """
        return await self.store.get_latest_snapshot(entity_id)

    async def export_compressed_checkpoint(self, entity_id: str) -> bytes:
        """
        [AX COMPRESSED TRANSPORT]: Encapsulates the absolute state + anchor event 
        into a portable zlib-compressed binary payload for multi-node handoff.
        """
        # 1. Retrieve physical snapshot
        snap = await self.get_latest_snapshot(entity_id)
        if not snap:
            raise ValueError(f"Cannot export checkpoint: No snapshot found for entity '{entity_id}'")

        last_event_id = snap["last_event_id"]

        # 2. Retrieve anchoring cryptographic event to transport logical_clock metadata
        anchor_event = await self.event_engine.get_event(last_event_id)
        if not anchor_event:
            raise ValueError(f"Corrupt checkpoint lineage: Anchor event '{last_event_id}' not found in event store.")

        # 3. Construct dense transport manifest
        manifest = {
            "entity_id": entity_id,
            "snapshot": snap,
            "anchor_event_json": anchor_event.model_dump_json()
        }

        # 4. Maximize bandwidth via zlib (level 9)
        raw_json = json.dumps(manifest, ensure_ascii=False)
        return zlib.compress(raw_json.encode("utf-8"), level=9)

    async def import_compressed_checkpoint(self, compressed_payload: bytes) -> None:
        """
        [AX DISTRIBUTED HYDRATION]: Ingests portable checkpoint, injecting BOTH the
        local snapshot state AND the anchoring cryptographic event into the destination node.
        Ensures StateEngine can execute immediate Fast-Forward-Replay zero-lag.
        """
        # 1. Decompress and inflate manifest
        raw_json = zlib.decompress(compressed_payload).decode("utf-8")
        manifest = json.loads(raw_json)

        entity_id = manifest["entity_id"]
        snap = manifest["snapshot"]
        anchor_json = manifest["anchor_event_json"]

        # 2. Ingest anchor event directly into raw store to bridge the causal gap
        # (Using store.append bypasses emission sealing to preserve the pre-existing hash)
        anchor_event = parse_event_from_json(anchor_json)
        await self.event_engine.store.append(anchor_event)

        # 3. Store physical snapshot
        await self.store.save_snapshot(
            entity_id,
            state=snap["state"],
            last_event_id=snap["last_event_id"],
            snapshot_type=snap.get("snapshot_type", "state")
        )
