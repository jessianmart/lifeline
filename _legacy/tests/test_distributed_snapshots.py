import unittest
import asyncio
import os
from datetime import datetime, timezone

from lifeline.core.events import SystemEvent
from lifeline.adapters.storage.sqlite import SQLiteEventStore, SQLiteSnapshotStore
from lifeline.engines.event_engine import EventEngine
from lifeline.engines.state_engine import StateEngine
from lifeline.engines.snapshot_engine import SnapshotEngine

class TestDistributedSnapshots(unittest.IsolatedAsyncioTestCase):
    """
    Validates portable distributed state checkpoints between physically isolated nodes.
    Simulates an agent handoff from Node A to Node B over distinct databases.
    """

    def setUp(self):
        self.db_a = "test_node_a.db"
        self.db_b = "test_node_b.db"

    def tearDown(self):
        # Purge physical test artifact DBs
        for db in [self.db_a, self.db_b]:
            if os.path.exists(db):
                try: os.remove(db)
                except: pass

    async def test_multi_node_checkpoint_handoff(self):
        # ---------------------------------------------------------
        # PHASE 1: NODE A Initialization and Event Sourcing
        # ---------------------------------------------------------
        store_a = SQLiteEventStore(self.db_a)
        snap_store_a = SQLiteSnapshotStore(self.db_a)
        await store_a.initialize()
        await snap_store_a.initialize()

        event_engine_a = EventEngine(store_a)
        state_engine_a = StateEngine(event_engine_a, snap_store_a)
        snapshot_engine_a = SnapshotEngine(snap_store_a, state_engine_a, event_engine_a)

        # Register dummy reducer for accumulation testing
        def dummy_accumulate(state, event):
            val = event.execution_metadata.get("value", 0)
            state["total"] = state.get("total", 0) + val
            return state
        
        state_engine_a.register_reducer("system", dummy_accumulate)

        # Append 2 events sequentially
        workflow_id = "workflow_xyz"
        
        ev1 = SystemEvent(
            logical_clock=1,
            timestamp=datetime.now(timezone.utc),
            workflow_id=workflow_id,
            action="TEST_ADD",
            execution_metadata={"value": 10}
        )
        ev1.seal([], 1)
        ev1_id = ev1.event_id
        await store_a.append(ev1)

        ev2 = SystemEvent(
            logical_clock=2,
            timestamp=datetime.now(timezone.utc),
            workflow_id=workflow_id,
            action="TEST_ADD",
            execution_metadata={"value": 20}
        )
        ev2.seal([ev1_id], 2)
        ev2_id = ev2.event_id
        await store_a.append(ev2)

        # Node A takes checkpoint after ev2
        current_state_a = await state_engine_a.rebuild_workflow_state(workflow_id)
        self.assertEqual(current_state_a["total"], 30)

        await snapshot_engine_a.create_snapshot(
            entity_id=workflow_id,
            current_state=current_state_a,
            last_event_id=ev2_id
        )

        # ---------------------------------------------------------
        # PHASE 2: Binary Extraction
        # ---------------------------------------------------------
        # Node A exports portable binary bytes
        portable_bytes = await snapshot_engine_a.export_compressed_checkpoint(workflow_id)
        self.assertIsInstance(portable_bytes, bytes)
        self.assertGreater(len(portable_bytes), 0)

        # ---------------------------------------------------------
        # PHASE 3: NODE B Isolation Hydration
        # ---------------------------------------------------------
        # Initialize Node B - physically separated SQLite!
        store_b = SQLiteEventStore(self.db_b)
        snap_store_b = SQLiteSnapshotStore(self.db_b)
        await store_b.initialize()
        await snap_store_b.initialize()

        event_engine_b = EventEngine(store_b)
        state_engine_b = StateEngine(event_engine_b, snap_store_b)
        state_engine_b.register_reducer("system", dummy_accumulate)
        
        snapshot_engine_b = SnapshotEngine(snap_store_b, state_engine_b, event_engine_b)

        # Before import: State on Node B should be completely EMPTY
        state_before = await state_engine_b.rebuild_workflow_state(workflow_id)
        self.assertEqual(state_before, {})

        # Node B imports binary package directly!
        await snapshot_engine_b.import_compressed_checkpoint(portable_bytes)

        # ---------------------------------------------------------
        # PHASE 4: Fast-Forward Autonomous Rebuild
        # ---------------------------------------------------------
        # Verify Node B's StateEngine can resolve the snapshot and anchoring event
        reconstructed_state_b = await state_engine_b.rebuild_workflow_state(workflow_id)
        
        # Crucial Assertion: Node B reconstructed the complete historical accumulated state
        # purely via the exported snapshot AND its imported anchor event!
        self.assertEqual(reconstructed_state_b["total"], 30)
        
        # Verify that event ev_01 does NOT exist on Node B (proving no full replay occurred)
        missing_ev1 = await event_engine_b.get_event(ev1_id)
        self.assertIsNone(missing_ev1, "Node B should not have received physical historical logs of ev_01!")
        
        # Verify that anchor ev_02 DOES exist locally for clock mapping
        anchor_present = await event_engine_b.get_event(ev2_id)
        self.assertIsNotNone(anchor_present, "Anchor event ev_02 MUST exist locally on Node B for Fast-Forward anchors!")

if __name__ == "__main__":
    unittest.main()
