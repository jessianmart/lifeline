"""Teste MCP AO VIVO: sobe o servidor Lifeline (subprocesso, stdio) e fala com ele por um
cliente MCP REAL — o mesmo protocolo que o Claude Code usa. Exercita o round-trip inteiro:
initialize → list_tools → list_resources → call_tool(append) → read_resource(context) →
call_tool(recall). Usa um ledger TEMP para não poluir a line real.

    python scripts/mcp_live_test.py
"""
import asyncio
import os
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

V2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def main():
    tmp = tempfile.mkdtemp()
    env = {
        **os.environ,
        "PYTHONPATH": V2,
        "PYTHONIOENCODING": "utf-8",
        "LIFELINE_DB": os.path.join(tmp, "ledger.db"),
        "LIFELINE_OUT": os.path.join(tmp, "LIFELINE.md"),
        "LIFELINE_AUTHOR": "mcp-live-test",
    }
    params = StdioServerParameters(command=sys.executable, args=["-m", "lifeline.mcp_server"],
                                   env=env, cwd=V2)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("[OK] initialize — handshake MCP completo")

            tools = [t.name for t in (await session.list_tools()).tools]
            print("[OK] tools:", tools)
            resources = [str(r.uri) for r in (await session.list_resources()).resources]
            print("[OK] resources:", resources)

            # ESCRITA via protocolo MCP (como o Claude faria ao trabalhar)
            r1 = await session.call_tool("lifeline_append", {
                "kind": "bootstrap", "summary": "Projeto Mercurio — API de cobranca recorrente",
                "body": "MVP multi-tenant.", "agent": "claude-code",
                "provider": "anthropic", "model": "claude-opus-4-8"})
            print("[OK] append #1:", r1.content[0].text)
            r2 = await session.call_tool("lifeline_append", {
                "kind": "decision", "summary": "Banco de dados: PostgreSQL",
                "body": "ACID exigido por cobranca.", "agent": "claude-code",
                "provider": "anthropic", "model": "claude-opus-4-8"})
            print("[OK] append #2:", r2.content[0].text)

            # LEITURA via protocolo MCP (como o Claude faria ao conectar)
            ctx = await session.read_resource("lifeline://project/context")
            text = ctx.contents[0].text
            print(f"[OK] read_resource: contexto de {len(text)} chars | "
                  f"tem 'Mercurio'={('Mercurio' in text)} tem 'PostgreSQL'={('PostgreSQL' in text)}")

            # RECALL via protocolo MCP
            rec = await session.call_tool("lifeline_recall", {"query": "qual banco de dados", "k": 3})
            print("[OK] recall:", rec.content[0].text.replace(chr(10), " | "))

    print("\n=== ROUND-TRIP MCP LIVE (cliente real <-> servidor) COMPLETO ===")


if __name__ == "__main__":
    asyncio.run(main())
