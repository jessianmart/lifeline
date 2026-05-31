"""Prova a CLI (o caminho de append do novo fluxo): log encadeia, regenera, e verifica."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifeline.cli import (  # noqa: E402
    cmd_log, cmd_verify, cmd_rebuild, cmd_lines, resolve_paths, DEFAULT_DB, DEFAULT_OUT,
)


class TestCLI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, ".lifeline", "ledger.db")
        self.out = os.path.join(self.dir, "LIFELINE.md")

    async def asyncTearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    async def _log(self, **kw):
        base = dict(db=self.db, out=self.out, body="", author="a", agent="claude-code",
                    provider="anthropic", model="m", parents=None)
        base.update(kw)
        return await cmd_log(**base)

    async def test_log_chains_and_writes(self):
        e1, ins1, n1 = await self._log(kind="bootstrap", summary="Funda X")
        self.assertTrue(ins1)
        self.assertEqual(n1, 1)
        self.assertTrue(os.path.exists(self.out))

        e2, ins2, n2 = await self._log(kind="decision", summary="usar Y", body="porquê")
        self.assertEqual(n2, 2)
        self.assertEqual(e2.parents, [e1.id])  # encadeou no head automaticamente

        with open(self.out, encoding="utf-8") as f:
            md = f.read()
        self.assertIn("usar Y", md)
        self.assertIn("- **id**:", md)

    async def test_verify_passes(self):
        await self._log(kind="bootstrap", summary="X")
        await self._log(kind="decision", summary="Y")
        ok, n = await cmd_verify(self.db)
        self.assertTrue(ok)
        self.assertEqual(n, 2)

    async def test_rebuild_is_stable(self):
        await self._log(kind="bootstrap", summary="X")
        await self._log(kind="feature", summary="Z")
        with open(self.out, encoding="utf-8") as f:
            first = f.read()
        await cmd_rebuild(self.db, self.out)
        with open(self.out, encoding="utf-8") as f:
            second = f.read()
        self.assertEqual(first, second)

    def test_resolve_paths(self):
        # --line mapeia ledger E view juntos; sem --line, usa os defaults
        self.assertEqual(resolve_paths("backend", DEFAULT_DB, DEFAULT_OUT),
                         (os.path.join(".lifeline", "backend.db"), "LIFELINE.backend.md"))
        self.assertEqual(resolve_paths(None, "x.db", "y.md"), ("x.db", "y.md"))

    async def test_named_lines_do_not_collide(self):
        root = os.path.join(self.dir, ".lifeline")
        db_a, out_a = os.path.join(root, "backend.db"), os.path.join(self.dir, "LIFELINE.backend.md")
        db_b, out_b = os.path.join(root, "research.db"), os.path.join(self.dir, "LIFELINE.research.md")
        await cmd_log(db_a, out_a, "decision", "usar gRPC", "", "a", "x", "p", "m", None)
        await cmd_log(db_b, out_b, "note", "conversa: onboarding simples", "", "a", "x", "p", "m", None)

        self.assertTrue(os.path.exists(out_a) and os.path.exists(out_b))
        with open(out_a, encoding="utf-8") as f:
            ta = f.read()
        with open(out_b, encoding="utf-8") as f:
            tb = f.read()
        self.assertIn("usar gRPC", ta)
        self.assertNotIn("usar gRPC", tb)          # views não se sobrepõem
        self.assertIn("conversa", tb)
        self.assertNotIn("conversa", ta)

    async def test_lines_lists_each(self):
        root = os.path.join(self.dir, ".lifeline")
        await cmd_log(os.path.join(root, "a.db"), os.path.join(self.dir, "LIFELINE.a.md"),
                      "note", "x", "", "a", "x", "p", "m", None)
        await cmd_log(os.path.join(root, "b.db"), os.path.join(self.dir, "LIFELINE.b.md"),
                      "note", "y", "", "a", "x", "p", "m", None)
        rows = await cmd_lines(root)
        self.assertEqual({n for n, _ in rows}, {"a", "b"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
