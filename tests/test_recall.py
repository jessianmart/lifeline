"""Prova a Camada 3: embedder lexical determinístico, busca por relevância, ancorada."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifeline.entry import Entry              # noqa: E402
from lifeline.store import SQLiteEventStore   # noqa: E402
from lifeline.recall import (  # noqa: E402
    LexicalEmbedder, SentenceTransformerEmbedder, SemanticRecall, make_embedder,
)


class _FakeST:
    """Modelo fake (sem baixar nada): mapeia texto→vetor; emula SentenceTransformer.encode."""
    def __init__(self, mapping, dim=3):
        self.mapping, self.dim = mapping, dim

    def encode(self, text, normalize_embeddings=True):
        return self.mapping.get(text, [0.0] * self.dim)


def _has_st():
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


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


class TestDenseEmbedder(unittest.TestCase):
    """#0029 — embedder semântico denso (opt-in). Default segue lexical (zero-dep)."""

    def test_make_embedder_default_is_lexical(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsInstance(make_embedder(), LexicalEmbedder)
            self.assertIsInstance(make_embedder("lexical"), LexicalEmbedder)

    def test_make_embedder_dense_and_model_name(self):
        self.assertIsInstance(make_embedder("dense"), SentenceTransformerEmbedder)
        e = make_embedder("all-mpnet-base-v2")
        self.assertIsInstance(e, SentenceTransformerEmbedder)
        self.assertEqual(e._model_name, "all-mpnet-base-v2")

    def test_make_embedder_reads_env(self):
        with mock.patch.dict(os.environ, {"LIFELINE_EMBEDDER": "dense"}):
            self.assertIsInstance(make_embedder(), SentenceTransformerEmbedder)

    def test_dense_embed_and_cosine_with_fake_model(self):
        v1, v2 = [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]
        emb = SentenceTransformerEmbedder(_model=_FakeST({"a": v1, "b": v1, "c": v2}))
        self.assertEqual(emb.embed("a"), v1)                                  # não baixou nada
        self.assertAlmostEqual(emb.similarity(emb.embed("a"), emb.embed("b")), 1.0)  # iguais
        self.assertAlmostEqual(emb.similarity(emb.embed("a"), emb.embed("c")), 0.0)  # ortogonais

    def test_missing_dep_raises_clear_error(self):
        emb = SentenceTransformerEmbedder()   # sem _model injetado
        if _has_st():
            self.skipTest("sentence-transformers instalado — caminho de erro não se aplica")
        with self.assertRaises(ImportError):
            emb.embed("qualquer")             # lazy import falha com mensagem do extra


class TestSemanticRecallDense(unittest.IsolatedAsyncioTestCase):
    async def test_recall_ranks_by_meaning_with_dense(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        store = SQLiteEventStore(os.path.join(d, "t.db"))
        await store.initialize()
        await store.append(Entry(author="a", kind="decision", summary="db", body=""))
        await store.append(Entry(author="a", kind="decision", summary="auth", body=""))
        # fake: "db\n" perto de "database"; "auth\n" longe (mesmo SEM token compartilhado)
        emb = SentenceTransformerEmbedder(_model=_FakeST(
            {"db\n": [1.0, 0.0], "auth\n": [0.0, 1.0], "database": [0.9, 0.1]}, dim=2))
        hits = await SemanticRecall(store, emb).search("database", k=2)
        self.assertEqual(hits[0]["summary"], "db")   # ranqueado por significado (cosseno), via o port


@unittest.skipUnless(_has_st(), "instale sentence-transformers ([embeddings]) p/ o teste real do denso")
class TestDenseEmbedderLive(unittest.TestCase):
    def test_semantic_relatedness(self):
        emb = SentenceTransformerEmbedder()
        q = emb.embed("which database do we use")
        related = emb.similarity(q, emb.embed("we chose PostgreSQL for storage"))
        unrelated = emb.similarity(q, emb.embed("the CI pipeline runs on Tuesdays"))
        self.assertGreater(related, unrelated)   # significado, não palavra


if __name__ == "__main__":
    unittest.main(verbosity=2)
