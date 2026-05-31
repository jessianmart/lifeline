"""Prova o ledger: roundtrip, idempotência (id e dedup_key), ordem, navegação no DAG."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifeline.entry import Entry          # noqa: E402
from lifeline.store import SQLiteEventStore  # noqa: E402


class TestSQLiteEventStore(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = SQLiteEventStore(os.path.join(self.dir, "t.db"))
        await self.store.initialize()

    async def asyncTearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def mk(self, **kw):
        base = dict(kind="note", author="a", summary="s")
        base.update(kw)
        return Entry(**base)

    async def test_append_get_roundtrip(self):
        e = self.mk(summary="hello", body="world")
        self.assertTrue(await self.store.append(e))
        got = await self.store.get(e.id)
        self.assertIsNotNone(got)
        self.assertEqual(got.id, e.id)
        self.assertEqual(got.summary, "hello")
        self.assertEqual(got.body, "world")
        self.assertTrue(got.verify())  # sobrevive ao roundtrip e o id ainda bate

    async def test_append_idempotent_by_id(self):
        e = self.mk(summary="dup")
        self.assertTrue(await self.store.append(e))
        self.assertFalse(await self.store.append(e))  # mesmo id → não duplica
        n = len([x async for x in self.store.stream()])
        self.assertEqual(n, 1)

    async def test_dedup_key_idempotency(self):
        a = self.mk(summary="x", dedup_key="k")
        b = self.mk(summary="y", dedup_key="k")  # id diferente, mesma dedup_key
        self.assertNotEqual(a.id, b.id)
        self.assertTrue(await self.store.append(a))
        self.assertFalse(await self.store.append(b))  # a dedup_key bloqueia o 2º

    async def test_stream_insertion_order(self):
        ids = []
        for i in range(3):
            e = self.mk(summary=f"s{i}")
            await self.store.append(e)
            ids.append(e.id)
        streamed = [e.id async for e in self.store.stream()]
        self.assertEqual(streamed, ids)

    async def test_dag_navigation(self):
        root = self.mk(summary="root")
        await self.store.append(root)
        child = self.mk(summary="child", parents=[root.id])
        await self.store.append(child)
        self.assertEqual([k.id for k in await self.store.children(root.id)], [child.id])
        self.assertEqual([p.id for p in await self.store.parents(child.id)], [root.id])


if __name__ == "__main__":
    unittest.main(verbosity=2)
