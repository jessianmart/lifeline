"""Prova a redução de estado: projeção da verdade, supersessão por correção, autoria, reducer custom."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifeline.entry import Entry            # noqa: E402
from lifeline.store import SQLiteEventStore  # noqa: E402
from lifeline.state import StateEngine       # noqa: E402


class TestStateEngine(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = SQLiteEventStore(os.path.join(self.dir, "t.db"))
        await self.store.initialize()

    async def asyncTearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    async def _append(self, **kw):
        kw.setdefault("provider", "anthropic")
        kw.setdefault("model", "claude-x")
        e = Entry(author="a", agent="claude-code", **kw)
        await self.store.append(e)
        return e

    async def test_projection_truth(self):
        await self._append(kind="bootstrap", summary="Funda o projeto X")
        await self._append(kind="decision", summary="usa DAG")
        await self._append(kind="decision", summary="status como reducer")
        await self._append(kind="feature", summary="ledger pronto")

        st = await StateEngine(self.store).reduce()
        self.assertEqual(st["project"], "Funda o projeto X")
        self.assertEqual(st["entry_count"], 4)
        self.assertEqual(st["kinds"]["decision"], 2)
        self.assertEqual([d["summary"] for d in st["decisions"]],
                         ["usa DAG", "status como reducer"])
        self.assertNotIn("_superseded", st)

    async def test_authorship_is_projected(self):
        await self._append(kind="bootstrap", summary="X", provider="anthropic", model="claude-opus-4-8")
        await self._append(kind="decision", summary="d", provider="google", model="gemini-2")

        st = await StateEngine(self.store).reduce()
        self.assertEqual(st["project_by"], "anthropic/claude-opus-4-8")
        self.assertIn("google/gemini-2", st["contributors"])
        self.assertEqual(st["decisions"][0]["model"], "gemini-2")
        self.assertEqual(st["decisions"][0]["provider"], "google")

    async def test_correction_supersedes(self):
        d = await self._append(kind="decision", summary="usar NATS")
        await self._append(kind="decision", summary="usar Redis")
        await self._append(kind="correction", summary="NATS cancelado", parents=[d.id])

        st = await StateEngine(self.store).reduce()
        summaries = [x["summary"] for x in st["decisions"]]
        self.assertIn("usar Redis", summaries)
        self.assertNotIn("usar NATS", summaries)

    async def test_custom_reducer(self):
        await self._append(kind="note", summary="n1")
        await self._append(kind="note", summary="n2")

        def count_notes(state, e):
            s = dict(state)
            if e.kind == "note":
                s["notes"] = s.get("notes", 0) + 1
            return s

        eng = StateEngine(self.store)
        eng.register(count_notes)
        st = await eng.reduce()
        self.assertEqual(st["notes"], 2)

    async def test_open_threads_collected_and_closed(self):
        o = await self._append(kind="open", summary="implementar recall")
        await self._append(kind="open", summary="política de embedding")
        st = await StateEngine(self.store).reduce()
        self.assertEqual([x["summary"] for x in st["open_items"]],
                         ["implementar recall", "política de embedding"])
        # fechar o primeiro via correction referenciando seu hash (Lei #2)
        await self._append(kind="correction", summary="recall feito", parents=[o.id])
        st2 = await StateEngine(self.store).reduce()
        self.assertEqual([x["summary"] for x in st2["open_items"]], ["política de embedding"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
