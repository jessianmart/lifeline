"""Staging — a fila de PROPOSTAS pendentes (HITL). Separada da line: só o aprovado vira
`Entry` no ledger. É o "git stage" do raciocínio.

Fluxo: a IA `propose` (async, leve, captura intent+porquê no momento da decisão) → entra
aqui como pendente, SEM latência e SEM tocar na line → o humano revisa em lote e aprova/
rejeita (HITL, fora do hot path) → aprovado sela na line (append-only, content-addressed).

Vive na MESMA db da line, em tabela própria (`proposals`) — a line (`entries`) só recebe
o que foi aprovado.
"""
import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional

import aiosqlite


class StagingStore:
    def __init__(self, db_path: str):
        self.path = db_path

    def _conn(self):
        return aiosqlite.connect(self.path, timeout=30.0)

    async def initialize(self) -> None:
        async with self._conn() as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS proposals (
                    pid       INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts        TEXT NOT NULL,
                    status    TEXT NOT NULL DEFAULT 'pending',
                    kind      TEXT NOT NULL,
                    author    TEXT, agent TEXT, provider TEXT, model TEXT,
                    summary   TEXT NOT NULL,
                    body      TEXT,
                    parents   TEXT NOT NULL
                )
            """)
            await db.commit()

    async def propose(self, *, kind, summary, body, author, agent, provider, model, parents=None) -> int:
        """Enfileira uma proposta pendente. Rápido e não-bloqueante (não toca na line)."""
        async with self._conn() as db:
            cur = await db.execute(
                "INSERT INTO proposals (ts, status, kind, author, agent, provider, model, summary, body, parents) "
                "VALUES (?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), kind, author, agent, provider, model,
                 summary, body or "", json.dumps(parents or [])),
            )
            await db.commit()
            return cur.lastrowid

    async def pending(self) -> List[Dict]:
        async with self._conn() as db:
            db.row_factory = sqlite3.Row
            async with db.execute("SELECT * FROM proposals WHERE status='pending' ORDER BY pid") as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def get(self, pid: int) -> Optional[Dict]:
        async with self._conn() as db:
            db.row_factory = sqlite3.Row
            async with db.execute("SELECT * FROM proposals WHERE pid=?", (pid,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def set_status(self, pid: int, status: str) -> None:
        async with self._conn() as db:
            await db.execute("UPDATE proposals SET status=? WHERE pid=?", (status, pid))
            await db.commit()
