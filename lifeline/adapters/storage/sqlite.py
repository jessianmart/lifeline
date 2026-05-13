import json
import sqlite3
from typing import AsyncIterator, List, Optional

import aiosqlite

from lifeline.core.events import (
    EventBase, SystemEvent, WorkflowEvent, AgentEvent, 
    ToolExecutionEvent, WorkflowStateTransitionEvent, FailureEvent, BranchMergeEvent
)
from lifeline.core.types import EventID, WorkflowID, AgentID
from .base import AbstractEventStore, AbstractSnapshotStore

class SQLiteEventStore(AbstractEventStore):
    def __init__(self, db_path: str = "lifeline_dev.db"):
        self.db_path = db_path

    async def initialize(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Base Node Table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    logical_clock INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    workflow_id TEXT,
                    agent_id TEXT,
                    workflow_node_id TEXT,
                    schema_version TEXT NOT NULL,
                    deduplication_key TEXT,
                    payload JSON NOT NULL
                )
            """)
            # Edge Table for Graph Operations (Lineage)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS event_edges (
                    parent_id TEXT NOT NULL,
                    child_id TEXT NOT NULL,
                    PRIMARY KEY (parent_id, child_id),
                    FOREIGN KEY(child_id) REFERENCES events(event_id) ON DELETE CASCADE
                )
            """)
            
            # High-performance indices
            await db.execute("CREATE INDEX IF NOT EXISTS idx_wf_clock ON events(workflow_id, logical_clock)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_agent_clock ON events(agent_id, logical_clock)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_edges_child ON event_edges(child_id)")
            await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_dedup ON events(deduplication_key) WHERE deduplication_key IS NOT NULL")
            await db.commit()

    def _parse_event(self, event_type: str, payload_json: str) -> EventBase:
        payload = json.loads(payload_json)
        if event_type == "system":
            return SystemEvent(**payload)
        elif event_type == "workflow":
            return WorkflowEvent(**payload)
        elif event_type == "state_transition":
            return WorkflowStateTransitionEvent(**payload)
        elif event_type == "agent":
            return AgentEvent(**payload)
        elif event_type == "tool_execution":
            return ToolExecutionEvent(**payload)
        elif event_type == "failure":
            return FailureEvent(**payload)
        elif event_type == "branch_merge":
            return BranchMergeEvent(**payload)
        else:
            return EventBase(**payload)

    async def append(self, event: EventBase) -> None:
        payload_json = event.model_dump_json()
        event_type = getattr(event, "event_type", "base")
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO events (
                        event_id, event_type, logical_clock, timestamp, 
                        workflow_id, agent_id, workflow_node_id, schema_version, deduplication_key, payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event_type,
                        event.logical_clock,
                        event.timestamp.isoformat(),
                        event.workflow_id,
                        event.agent_id,
                        event.workflow_node_id,
                        event.schema_version,
                        getattr(event, "deduplication_key", None),
                        payload_json
                    )
                )
                
                # Insert operational graph edges
                if event.parent_event_ids:
                    edges = [(parent, event.event_id) for parent in event.parent_event_ids]
                    await db.executemany(
                        "INSERT OR IGNORE INTO event_edges (parent_id, child_id) VALUES (?, ?)",
                        edges
                    )
                await db.commit()
        except sqlite3.IntegrityError:
            pass # Idempotency check on append-only

    async def append_batch(self, events: List[EventBase]) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            node_batch = []
            edge_batch = []
            for event in events:
                payload_json = event.model_dump_json()
                event_type = getattr(event, "event_type", "base")
                node_batch.append((
                    event.event_id,
                    event_type,
                    event.logical_clock,
                    event.timestamp.isoformat(),
                    event.workflow_id,
                    event.agent_id,
                    event.workflow_node_id,
                    event.schema_version,
                    getattr(event, "deduplication_key", None),
                    payload_json
                ))
                for parent in event.parent_event_ids:
                    edge_batch.append((parent, event.event_id))
            
            try:
                await db.executemany(
                    """
                    INSERT OR IGNORE INTO events (
                        event_id, event_type, logical_clock, timestamp, 
                        workflow_id, agent_id, workflow_node_id, schema_version, deduplication_key, payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    node_batch
                )
                if edge_batch:
                    await db.executemany(
                        "INSERT OR IGNORE INTO event_edges (parent_id, child_id) VALUES (?, ?)",
                        edge_batch
                    )
                await db.commit()
            except sqlite3.Error:
                pass

    async def get_event(self, event_id: EventID) -> Optional[EventBase]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT event_type, payload FROM events WHERE event_id = ?", (event_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._parse_event(row[0], row[1])
        return None

    def get_workflow_stream(self, workflow_id: WorkflowID, since_logical_clock: int = -1) -> AsyncIterator[EventBase]:
        # Define an internal generator to return proper async iterator
        async def generator():
            async with aiosqlite.connect(self.db_path) as db:
                # Sort primarily by logical_clock for true causality sequencing
                async with db.execute(
                    """
                    SELECT event_type, payload FROM events 
                    WHERE workflow_id = ? AND logical_clock > ? 
                    ORDER BY logical_clock ASC, timestamp ASC
                    """, 
                    (workflow_id, since_logical_clock)
                ) as cursor:
                    async for row in cursor:
                        yield self._parse_event(row[0], row[1])
        return generator()

    def get_agent_stream(self, agent_id: AgentID, since_logical_clock: int = -1) -> AsyncIterator[EventBase]:
        async def generator():
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    """
                    SELECT event_type, payload FROM events 
                    WHERE agent_id = ? AND logical_clock > ? 
                    ORDER BY logical_clock ASC, timestamp ASC
                    """, 
                    (agent_id, since_logical_clock)
                ) as cursor:
                    async for row in cursor:
                        yield self._parse_event(row[0], row[1])
        return generator()

    async def get_latest_workflow_event(self, workflow_id: WorkflowID) -> Optional[EventBase]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT event_type, payload FROM events WHERE workflow_id = ? ORDER BY logical_clock DESC, timestamp DESC LIMIT 1", 
                (workflow_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._parse_event(row[0], row[1])
        return None

    async def get_latest_agent_event(self, agent_id: AgentID) -> Optional[EventBase]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT event_type, payload FROM events WHERE agent_id = ? ORDER BY logical_clock DESC, timestamp DESC LIMIT 1", 
                (agent_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._parse_event(row[0], row[1])
        return None

    # Graph capabilities
    async def get_parent_events(self, child_id: EventID) -> List[EventBase]:
        async with aiosqlite.connect(self.db_path) as db:
            query = """
                SELECT e.event_type, e.payload 
                FROM event_edges edge 
                JOIN events e ON edge.parent_id = e.event_id
                WHERE edge.child_id = ?
            """
            async with db.execute(query, (child_id,)) as cursor:
                rows = await cursor.fetchall()
                return [self._parse_event(row[0], row[1]) for row in rows]

    async def get_child_events(self, parent_id: EventID) -> List[EventBase]:
        async with aiosqlite.connect(self.db_path) as db:
            query = """
                SELECT e.event_type, e.payload 
                FROM event_edges edge 
                JOIN events e ON edge.child_id = e.event_id
                WHERE edge.parent_id = ?
            """
            async with db.execute(query, (parent_id,)) as cursor:
                rows = await cursor.fetchall()
                return [self._parse_event(row[0], row[1]) for row in rows]


class SQLiteSnapshotStore(AbstractSnapshotStore):
    def __init__(self, db_path: str = "lifeline_dev.db"):
        self.db_path = db_path

    async def initialize(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    entity_id TEXT PRIMARY KEY,
                    last_event_id TEXT NOT NULL,
                    snapshot_type TEXT NOT NULL,
                    state JSON NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            await db.commit()

    async def save_snapshot(self, entity_id: str, state: dict, last_event_id: EventID, snapshot_type: str = "state") -> None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        state_json = json.dumps(state)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO snapshots (entity_id, last_event_id, snapshot_type, state, timestamp)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(entity_id) DO UPDATE SET
                    last_event_id = excluded.last_event_id,
                    snapshot_type = excluded.snapshot_type,
                    state = excluded.state,
                    timestamp = excluded.timestamp
                """,
                (entity_id, last_event_id, snapshot_type, state_json, now)
            )
            await db.commit()

    async def get_latest_snapshot(self, entity_id: str) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT state, last_event_id, snapshot_type FROM snapshots WHERE entity_id = ?", 
                (entity_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {"state": json.loads(row[0]), "last_event_id": row[1], "snapshot_type": row[2]}
        return None
