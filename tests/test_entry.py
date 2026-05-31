"""Prova que o Entry obedece a Lei #3 (content-addressing determinístico)."""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifeline.entry import Entry  # noqa: E402


def make(**kw):
    base = dict(kind="decision", author="a@x", agent="claude-code",
                provider="anthropic", model="claude-opus-4-8",
                summary="s", body="b")
    base.update(kw)
    return Entry(**base)


class TestEntryDeterminism(unittest.TestCase):
    def test_id_is_stable_across_ts(self):
        """Mesmo conteúdo em momentos diferentes → mesmo id (ts fora do hash)."""
        e1 = make()
        time.sleep(0.01)
        e2 = make()
        self.assertNotEqual(e1.ts, e2.ts)
        self.assertEqual(e1.id, e2.id)

    def test_id_sensitive_to_body(self):
        """Mudar o conteúdo muda o id."""
        self.assertNotEqual(make(body="x").id, make(body="y").id)

    def test_id_invariant_to_parent_order(self):
        """Pais [A,B] e [B,A] produzem o mesmo id (set causal, não lista)."""
        self.assertEqual(
            make(parents=["aaa", "bbb"]).id,
            make(parents=["bbb", "aaa"]).id,
        )

    def test_parents_change_id(self):
        self.assertNotEqual(make(parents=[]).id, make(parents=["aaa"]).id)

    def test_self_verifies(self):
        self.assertTrue(make(body="anything").verify())

    def test_dedup_key_excluded_from_id(self):
        """dedup_key é metadado de idempotência — não muda a identidade."""
        self.assertEqual(make(dedup_key="k1").id, make(dedup_key="k2").id)

    def test_stored_id_is_preserved(self):
        """Reconstruir com id explícito não recomputa (preserva o storage)."""
        e = Entry(id="deadbeef", kind="note", author="a", summary="s")
        self.assertEqual(e.id, "deadbeef")
        self.assertFalse(e.verify())  # id não bate com o conteúdo → detectável


if __name__ == "__main__":
    unittest.main(verbosity=2)
