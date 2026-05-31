"""Contrato MCP: o loop sem humano precisa de leitura (resource) E escrita (tools).
Cobre também a escolha de backend (local/remoto) e que a escrita continua HITL."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lifeline.mcp_server as srv     # noqa: E402
from lifeline import cli             # noqa: E402
from lifeline.mcp_server import mcp  # noqa: E402


class TestMCPContract(unittest.IsolatedAsyncioTestCase):
    async def test_write_tools_registered(self):
        names = [t.name for t in await mcp.list_tools()]
        self.assertIn("lifeline_append", names)           # escrita: anexar
        self.assertIn("lifeline_recontextualize", names)  # escrita: supersede
        self.assertIn("lifeline_recall", names)           # leitura: relevância

    async def test_context_resource_registered(self):
        uris = [str(r.uri) for r in await mcp.list_resources()]
        uris += [t.uriTemplate for t in await mcp.list_resource_templates()]
        self.assertTrue(any("lifeline://project/context" in u for u in uris))


class TestMCPBackendAndHITL(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.addCleanup(lambda: cli._STORE.update(kind="sqlite", line="ledger"))

    def test_configure_selects_backend_from_env(self):
        with mock.patch.dict(os.environ, {"LIFELINE_STORE": "supabase", "LIFELINE_LINE": "research"}):
            srv._configure()
        self.assertEqual(cli._STORE["kind"], "supabase")    # modo nuvem (remoto) escolhido por env
        self.assertEqual(cli._STORE["line"], "research")

    def test_configure_defaults_to_sqlite(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            srv._configure()
        self.assertEqual(cli._STORE["kind"], "sqlite")      # local por padrão (sem regressão)

    async def test_append_tool_is_hitl(self):
        # a tool de escrita PROPÕE (fila pendente), NÃO commita direto na line (HITL)
        cli._STORE.update(kind="sqlite", line="ledger")
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        self.addCleanup(setattr, srv, "_DB", srv._DB)        # restaura o _DB original
        db = os.path.join(d, ".lifeline", "ledger.db")
        srv._DB = db
        msg = await srv.lifeline_append("decision", "usar gRPC", "porque escala")
        self.assertIn("PENDENTE", msg)
        self.assertEqual(len(await cli.cmd_review(db)), 1)   # entrou na fila…
        _, n = await cli.cmd_verify(db)
        self.assertEqual(n, 0)                                # …e NÃO na line (0 entradas seladas)


if __name__ == "__main__":
    unittest.main(verbosity=2)
