"""Prova que o store é a fonte e a markdown é projeção fiel: round-trip = ponto fixo."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifeline.entry import Entry              # noqa: E402
from lifeline.store import SQLiteEventStore   # noqa: E402
from lifeline.ingest import ingest_text       # noqa: E402
from lifeline.projection import render_ledger_markdown  # noqa: E402


class TestProjectionRoundtrip(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    async def _store(self, name):
        s = SQLiteEventStore(os.path.join(self.dir, name))
        await s.initialize()
        return s

    async def test_roundtrip_is_fixed_point(self):
        s1 = await self._store("a.db")
        e1 = Entry(kind="bootstrap", author="a", provider="anthropic", model="m", summary="Funda X")
        await s1.append(e1)
        e2 = Entry(kind="decision", author="a", provider="google", model="gemini", summary="usar Y",
                   body="porque Z", parents=[e1.id])
        await s1.append(e2)
        # correção com pai explícito (DAG não-linear) precisa sobreviver ao round-trip
        e3 = Entry(kind="correction", author="a", provider="anthropic", model="m",
                   summary="Y cancelado", parents=[e2.id])
        await s1.append(e3)

        ids1 = [e.id async for e in s1.stream()]
        md = await render_ledger_markdown(s1)

        # store -> markdown -> store2
        s2 = await self._store("b.db")
        n = await ingest_text(md, s2)
        self.assertEqual(n, 3)
        ids2 = [e.id async for e in s2.stream()]

        # PONTO FIXO: ids estáveis e o DAG (parents) preservado
        self.assertEqual(ids1, ids2)
        e3b = await s2.get(e3.id)
        self.assertEqual(e3b.parents, [e2.id])

        # render de novo deve ser byte-idêntico
        md2 = await render_ledger_markdown(s2)
        self.assertEqual(md, md2)

    async def test_content_is_faithful(self):
        s = await self._store("c.db")
        await s.append(Entry(kind="decision", author="a", provider="anthropic",
                             model="claude", summary="DAG content-addressed", body="o porquê"))
        md = await render_ledger_markdown(s)
        self.assertIn("DAG content-addressed", md)
        self.assertIn("o porquê", md)
        self.assertIn("- **id**:", md)
        self.assertIn("- **parents**:", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
