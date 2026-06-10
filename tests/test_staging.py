"""Prova o fluxo HITL: propose (pendente, não na line) → review → approve (sela) / reject."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifeline.store import SQLiteEventStore                       # noqa: E402
from lifeline.cli import cmd_propose, cmd_review, cmd_approve, cmd_reject  # noqa: E402


class TestHITLFlow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, ".lifeline", "ledger.db")
        self.out = os.path.join(self.dir, "LIFELINE.md")

    async def asyncTearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    async def _ledger_count(self):
        s = SQLiteEventStore(self.db)
        await s.initialize()
        return len([e async for e in s.stream()])

    async def test_propose_is_pending_not_in_line(self):
        await cmd_propose(self.db, "decision", "usar gRPC", "porque escala melhor",
                          "ia", "claude-code", "anthropic", "m", None)
        pend = await cmd_review(self.db)
        self.assertEqual(len(pend), 1)
        self.assertEqual(pend[0]["summary"], "usar gRPC")
        self.assertEqual(await self._ledger_count(), 0)  # proposta NÃO está na line ainda

    async def test_approve_seals_into_line(self):
        await cmd_propose(self.db, "decision", "A", "porque A", "ia", "x", "p", "m", None)
        await cmd_propose(self.db, "note", "B", "porque B", "ia", "x", "p", "m", None)
        approved, n, duplicates, errors = await cmd_approve(self.db, self.out, ["all"])
        self.assertEqual(approved, 2)
        self.assertEqual(duplicates, 0)
        self.assertEqual(errors, [])
        self.assertEqual(await self._ledger_count(), 2)        # agora estão na line
        self.assertEqual(await cmd_review(self.db), [])         # nada mais pendente
        self.assertTrue(os.path.exists(self.out))               # view regenerada

    async def test_reject_discards(self):
        pid = await cmd_propose(self.db, "note", "lixo", "corpo qualquer", "ia", "x", "p", "m", None)
        await cmd_reject(self.db, [str(pid)])
        self.assertEqual(await cmd_review(self.db), [])
        self.assertEqual(await self._ledger_count(), 0)         # nunca entrou na line

    async def test_propose_requires_why(self):
        with self.assertRaises(ValueError):  # anti-sujeira: sem o porquê, recusa
            await cmd_propose(self.db, "decision", "sem corpo", "", "ia", "x", "p", "m", None)

    async def test_invalid_kind_rejected(self):
        with self.assertRaises(ValueError):
            await cmd_propose(self.db, "banana", "x", "y", "ia", "x", "p", "m", None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
