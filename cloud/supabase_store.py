"""EXPERIMENTAL — adapter Supabase (Tier 1). NÃO está no core testado (`lifeline/`):
não dá para testar sem um projeto Supabase real. Promova para o core, COM testes contra
um projeto, quando validado. Implementa o port `EventStore` sobre o PostgREST do Supabase
— então o resto do Lifeline (state, context, recall, CLI) funciona igual, só trocando o store.

Config por ambiente — NUNCA cole a service_role key em chat nem comite segredo:
    SUPABASE_URL=https://<ref>.supabase.co
    SUPABASE_KEY=<access token do usuário ou anon key>   # RLS scopa por auth.uid()

Pré-requisito: rodar `cloud/schema.sql` no SQL Editor do projeto.
"""
import json
import os
from typing import AsyncIterator, List, Optional

import httpx

from lifeline.entry import Entry
from lifeline.store import EventStore


class SupabaseEventStore(EventStore):
    def __init__(self, line: str = "ledger", url: Optional[str] = None, key: Optional[str] = None):
        self.line = line
        self.url = (url or os.environ["SUPABASE_URL"]).rstrip("/")
        self.key = key or os.environ["SUPABASE_KEY"]
        self.base = f"{self.url}/rest/v1/lifeline_entries"

    def _headers(self, extra=None):
        h = {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        if extra:
            h.update(extra)
        return h

    async def initialize(self) -> None:
        pass  # schema é criado uma vez via cloud/schema.sql (no SQL Editor)

    async def append(self, e: Entry) -> bool:
        row = {
            "line": self.line, "id": e.id, "ts": e.ts.isoformat(), "kind": e.kind,
            "summary": e.summary, "body": e.body, "parents": e.parents,
            "dedup_key": e.dedup_key, "payload": json.loads(e.model_dump_json()),
        }
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(self.base, json=row, headers=self._headers(
                {"Prefer": "resolution=ignore-duplicates,return=minimal"}))
        return r.status_code in (200, 201)  # ignore-duplicates → idempotente (content-addressed)

    async def get(self, entry_id: str) -> Optional[Entry]:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(self.base, headers=self._headers(), params={
                "line": f"eq.{self.line}", "id": f"eq.{entry_id}", "select": "payload"})
        rows = r.json()
        return Entry.model_validate_json(json.dumps(rows[0]["payload"])) if rows else None

    def stream(self) -> AsyncIterator[Entry]:
        async def _gen():
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.get(self.base, headers=self._headers(), params={
                    "line": f"eq.{self.line}", "select": "payload", "order": "seq.asc"})
            for row in r.json():
                yield Entry.model_validate_json(json.dumps(row["payload"]))
        return _gen()

    async def parents(self, entry_id: str) -> List[Entry]:
        e = await self.get(entry_id)
        out = []
        for pid in (e.parents if e else []):
            p = await self.get(pid)
            if p:
                out.append(p)
        return out

    async def children(self, entry_id: str) -> List[Entry]:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(self.base, headers=self._headers(), params={
                "line": f"eq.{self.line}", "parents": f'cs.["{entry_id}"]',
                "select": "payload", "order": "seq.asc"})
        return [Entry.model_validate_json(json.dumps(row["payload"])) for row in r.json()]
