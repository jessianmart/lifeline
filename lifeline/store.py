"""O ledger — Camada 1 (episódica): armazenamento append-only do DAG de Entries.

`EventStore` é a *costura* (port): o core depende só dela. O `SQLiteEventStore` é o
adapter local (OSS). Um `SupabaseEventStore` futuro implementa a MESMA interface,
sem tocar no núcleo — é assim que o modo nuvem entra sem inflar o core.
"""
import json
import sqlite3
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional

import aiosqlite

from lifeline.entry import Entry


class EventStore(ABC):
    """Port do ledger. Append-only; preserva ordem causal."""

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def append(self, entry: Entry) -> bool:
        """Anexa um Entry. Retorna False se já existia (idempotente por id e dedup_key)."""

    @abstractmethod
    async def get(self, entry_id: str) -> Optional[Entry]: ...

    @abstractmethod
    def stream(self) -> AsyncIterator[Entry]:
        """Todos os entries em ordem causal (ordem de inserção, single-writer)."""

    @abstractmethod
    async def parents(self, entry_id: str) -> List[Entry]: ...

    @abstractmethod
    async def children(self, entry_id: str) -> List[Entry]: ...


class SQLiteEventStore(EventStore):
    """Adapter local. WAL para throughput; tabela de arestas para o DAG; dedup único."""

    def __init__(self, path: str = "lifeline.db"):
        self.path = path

    def _conn(self):
        return aiosqlite.connect(self.path, timeout=30.0)

    async def initialize(self) -> None:
        async with self._conn() as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
                    id         TEXT UNIQUE NOT NULL,
                    ts         TEXT NOT NULL,
                    kind       TEXT NOT NULL,
                    dedup_key  TEXT,
                    parents    TEXT NOT NULL,
                    payload    TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    parent_id TEXT NOT NULL,
                    child_id  TEXT NOT NULL,
                    PRIMARY KEY (parent_id, child_id)
                )
            """)
            await db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_dedup "
                "ON entries(dedup_key) WHERE dedup_key IS NOT NULL"
            )
            await db.execute("CREATE INDEX IF NOT EXISTS idx_edges_child ON edges(child_id)")
            await db.commit()

    async def append(self, entry: Entry) -> bool:
        async with self._conn() as db:
            try:
                await db.execute(
                    "INSERT INTO entries (id, ts, kind, dedup_key, parents, payload) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (entry.id, entry.ts.isoformat(), entry.kind, entry.dedup_key,
                     json.dumps(entry.parents), entry.model_dump_json()),
                )
            except sqlite3.IntegrityError:
                # id já presente OU dedup_key já usada → idempotência silenciosa.
                return False
            if entry.parents:
                await db.executemany(
                    "INSERT OR IGNORE INTO edges (parent_id, child_id) VALUES (?, ?)",
                    [(p, entry.id) for p in entry.parents],
                )
            await db.commit()
            return True

    async def get(self, entry_id: str) -> Optional[Entry]:
        async with self._conn() as db:
            async with db.execute("SELECT payload FROM entries WHERE id = ?", (entry_id,)) as cur:
                row = await cur.fetchone()
                return Entry.model_validate_json(row[0]) if row else None

    def stream(self) -> AsyncIterator[Entry]:
        async def _gen():
            async with self._conn() as db:
                async with db.execute("SELECT payload FROM entries ORDER BY seq ASC") as cur:
                    async for row in cur:
                        yield Entry.model_validate_json(row[0])
        return _gen()

    async def _neighbors(self, query: str, entry_id: str) -> List[Entry]:
        async with self._conn() as db:
            async with db.execute(query, (entry_id,)) as cur:
                return [Entry.model_validate_json(r[0]) for r in await cur.fetchall()]

    async def parents(self, entry_id: str) -> List[Entry]:
        return await self._neighbors(
            "SELECT e.payload FROM edges g JOIN entries e ON g.parent_id = e.id "
            "WHERE g.child_id = ?", entry_id,
        )

    async def children(self, entry_id: str) -> List[Entry]:
        return await self._neighbors(
            "SELECT e.payload FROM edges g JOIN entries e ON g.child_id = e.id "
            "WHERE g.parent_id = ?", entry_id,
        )
