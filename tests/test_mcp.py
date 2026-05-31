"""Contrato MCP: o loop sem humano precisa de leitura (resource) E escrita (tools)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifeline.mcp_server import mcp  # noqa: E402


class TestMCPContract(unittest.IsolatedAsyncioTestCase):
    async def test_write_tools_registered(self):
        names = [t.name for t in await mcp.list_tools()]
        self.assertIn("lifeline_append", names)          # escrita: anexar
        self.assertIn("lifeline_recontextualize", names)  # escrita: supersede

    async def test_context_resource_registered(self):
        uris = [str(r.uri) for r in await mcp.list_resources()]
        uris += [t.uriTemplate for t in await mcp.list_resource_templates()]
        self.assertTrue(any("lifeline://project/context" in u for u in uris))


if __name__ == "__main__":
    unittest.main(verbosity=2)
