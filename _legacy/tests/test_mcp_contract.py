import unittest
from lifeline.adapters.mcp.server import mcp

class TestMCPContract(unittest.IsolatedAsyncioTestCase):
    """Ensures the Model Context Protocol server successfully registers critical interfaces."""
    
    async def test_mcp_registrations(self):
        # 1. Inspect asynchronously registered tools
        tools = await mcp.list_tools()
        tool_names = [t.name for t in tools]
        self.assertIn("get_workflow_status_tool", tool_names)
        self.assertIn("transition_workflow_state_tool", tool_names)
        
        # 2. Inspect asynchronously registered resource templates
        templates = await mcp.list_resource_templates()
        template_uris = [t.uriTemplate for t in templates]
        self.assertIn("lifeline://{db_path}/ledger", template_uris)
        self.assertIn("lifeline://{db_path}/dead_letters", template_uris)

if __name__ == "__main__":
    unittest.main()
