"""Ingere a própria LIFELINE.md e imprime o payload de contexto montado.

É o que o resource MCP `lifeline://project/context` devolveria a uma IA que conecta.
O teste de aceitação dá ESTE texto (e nada mais) a um agente sem contexto.
"""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifeline.store import SQLiteEventStore       # noqa: E402
from lifeline.state import StateEngine            # noqa: E402
from lifeline.context import ContextAssembler     # noqa: E402
from lifeline.ingest import ingest_markdown       # noqa: E402


async def main():
    here = os.path.dirname(os.path.abspath(__file__))
    md = os.path.join(os.path.dirname(here), "LIFELINE.md")

    tmp = tempfile.mkdtemp()
    store = SQLiteEventStore(os.path.join(tmp, "ledger.db"))
    await store.initialize()

    n = await ingest_markdown(md, store)
    payload = await ContextAssembler(StateEngine(store), budget_chars=4000).assemble()

    snap = os.path.join(os.path.dirname(here), "CONTEXT_SNAPSHOT.md")
    with open(snap, "w", encoding="utf-8") as f:
        f.write(payload)

    print(f"[ingeridas {n} entradas no ledger]")
    print(f"[snapshot escrito em {snap} — {len(payload)} chars]")


if __name__ == "__main__":
    asyncio.run(main())
