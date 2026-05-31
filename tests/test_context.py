"""Prova a montagem: payload responde o quê/por quê/decidido, mostra autoria, trunca explícito (Lei #6)."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifeline.entry import Entry            # noqa: E402
from lifeline.store import SQLiteEventStore  # noqa: E402
from lifeline.state import StateEngine       # noqa: E402
from lifeline.context import ContextAssembler  # noqa: E402


class TestContextAssembler(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = SQLiteEventStore(os.path.join(self.dir, "t.db"))
        await self.store.initialize()
        for kind, summary in [
            ("bootstrap", "Funda o Lifeline"),
            ("decision", "DAG content-addressed"),
            ("decision", "status como reducer"),
            ("feature", "ledger SQLite pronto"),
            ("open", "transplantar recall do SDK antigo"),
        ]:
            await self.store.append(Entry(
                author="a", agent="claude-code", provider="anthropic",
                model="claude-opus-4-8", kind=kind, summary=summary,
            ))
        self.engine = StateEngine(self.store)

    async def asyncTearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    async def test_payload_answers_what_why_next(self):
        text = await ContextAssembler(self.engine).assemble()
        self.assertIn("Funda o Lifeline", text)          # o quê
        self.assertIn("DAG content-addressed", text)      # por quê / decidido
        self.assertIn("status como reducer", text)        # por quê / decidido
        self.assertIn("ledger SQLite pronto", text)       # o que vem a seguir

    async def test_payload_shows_authorship(self):
        text = await ContextAssembler(self.engine).assemble()
        self.assertIn("claude-opus-4-8", text)            # qual modelo
        self.assertIn("anthropic", text)                  # qual provider
        self.assertIn("Contribuíram:", text)              # agregado de autoria

    async def test_payload_shows_open_threads(self):
        text = await ContextAssembler(self.engine).assemble()
        self.assertIn("Em aberto", text)
        self.assertIn("transplantar recall do SDK antigo", text)

    async def test_recent_marks_superseded(self):
        # uma thread aberta fechada por correção deve aparecer na "Recente" marcada (fix #0018)
        o = Entry(author="a", agent="claude-code", provider="anthropic",
                  model="m", kind="open", summary="thread efêmera X")
        await self.store.append(o)
        await self.store.append(Entry(author="a", agent="claude-code", provider="anthropic",
                                      model="m", kind="correction", summary="X resolvido", parents=[o.id]))
        text = await ContextAssembler(self.engine).assemble()
        self.assertIn("[fechado/revertido]", text)            # marcada como superseded
        # e não aparece mais como aberta
        self.assertNotIn("- `[" + o.id[:8] + "]` thread efêmera X", text)

    async def test_query_adds_relevant_section(self):
        from lifeline.recall import SemanticRecall
        recall = SemanticRecall(self.store)
        text = await ContextAssembler(self.engine).assemble(query="ledger sqlite", recall=recall)
        self.assertIn("Relevante para:", text)
        self.assertIn("ledger SQLite pronto", text)  # relevância lexical achou a entrada certa

    async def test_budget_truncation_is_explicit(self):
        text = await ContextAssembler(self.engine, budget_chars=120).assemble()
        self.assertLessEqual(len(text), 120)
        self.assertIn("truncado", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
