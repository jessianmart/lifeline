"""Prova a Camada 3: embedder lexical determinístico, busca por relevância, ancorada."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifeline.entry import Entry              # noqa: E402
from lifeline.store import SQLiteEventStore   # noqa: E402
from lifeline.recall import LexicalEmbedder, SemanticRecall  # noqa: E402


class TestEmbedder(unittest.TestCase):
    def test_deterministic_and_normalized(self):
        emb = LexicalEmbedder()
        a = emb.embed("banco de dados postgres")
        b = emb.embed("banco de dados postgres")
        self.assertEqual(a, b)                                       # determinístico
        self.assertAlmostEqual(emb.similarity(a, a), 1.0, places=6)  # L2-normalizado

    def test_overlap_scores_higher(self):
        emb = LexicalEmbedder()
        q = emb.embed("banco de dados")
        near = emb.embed("escolha do banco de dados principal")
        far = emb.embed("politica de autenticacao por token")
        self.assertGreater(emb.similarity(q, near), emb.similarity(q, far))

    def test_no_shared_tokens_is_zero(self):
        emb = LexicalEmbedder()
        a = emb.embed("kubernetes deploy aws")
        b = emb.embed("xkcd zzz qwerty")
        self.assertEqual(emb.similarity(a, b), 0.0)  # sem colisão (≠ hashing)


class TestSemanticRecall(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = SQLiteEventStore(os.path.join(self.dir, "t.db"))
        await self.store.initialize()
        for kind, summary in [
            ("decision", "Banco de dados PostgreSQL com particionamento"),
            ("decision", "Autenticacao por OAuth2 e JWT"),
            ("decision", "Deploy em Kubernetes na AWS"),
        ]:
            await self.store.append(Entry(author="a", agent="x", provider="p", model="m",
                                          kind=kind, summary=summary))

    async def asyncTearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    async def test_search_returns_relevant_anchored(self):
        recall = SemanticRecall(self.store)
        hits = await recall.search("qual banco de dados usamos", k=3)
        self.assertTrue(hits)
        self.assertIn("PostgreSQL", hits[0]["summary"])   # o mais relevante primeiro
        self.assertIn("id", hits[0])                       # ancorado ao evento
        self.assertGreater(hits[0]["score"], 0)

    async def test_no_overlap_returns_nothing(self):
        recall = SemanticRecall(self.store)
        hits = await recall.search("xkcd zzz qwerty nonsense", k=5)
        self.assertEqual(hits, [])  # honestidade: sem sobreposição, não inventa relevância


if __name__ == "__main__":
    unittest.main(verbosity=2)
