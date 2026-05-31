import asyncio
import os
import sys
from rich.console import Console
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from lifeline.core.events import SystemEvent
from lifeline.adapters.storage.sqlite import SQLiteEventStore
from lifeline.engines.event_engine import EventEngine
from lifeline.runtime.state_machine import WorkflowStateMachine

console = Console()

async def run_antigravity_mcp_client():
    console.rule("[bold magenta]🌌 ANTIGRAVITY MCP CLIENT SIMULATION 🌌")
    
    db_name = "antigravity_mcp_demo.db"
    # Use relative path to prevent Windows drive colons (C:) from breaking URI schema constraints!
    db_path = db_name
    
    if os.path.exists(db_name):
        try: os.remove(db_name)
        except: pass

    # 1. BOOTSTRAP WORKFLOW PHYSICALLY
    console.print("[cyan]Passo 1: Criando Workflow físico inicial (PENDING)...[/cyan]")
    store = SQLiteEventStore(db_name)
    await store.initialize()
    engine = EventEngine(store)
    sm = WorkflowStateMachine(engine)
    
    workflow_id = "wf_e2e_antigravity"
    # Initialize to PENDING
    await sm.transition(workflow_id, "PENDING", "CREATE", agent_id="BOOT_SCRIPT")
    console.print(f"[dim green]✔ Workflow [{workflow_id}] inicializado no ledger local.[/dim green]")

    # 2. SPAWN SERVER AND CONNECT VIA STDIO TRANSPORT
    console.print("\n[cyan]Passo 2: Instanciando servidor MCP local via Subprocess (STDIO)...[/cyan]")
    
    # Set PYTHONPATH so the subprocess can resolve the lifeline package!
    env_copy = os.environ.copy()
    env_copy["PYTHONPATH"] = os.path.abspath(".")
    
    server_params = StdioServerParameters(
        command="python",
        args=["lifeline/adapters/mcp/server.py"],
        env=env_copy
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 2.1 Perform official JSON-RPC Handshake
            console.print("[yellow]Executando handshake 'initialize' oficial...[/yellow]")
            await session.initialize()
            console.print("[bold green]✔ Handshake estabelecido com sucesso! Canal IPC ativo.[/bold green]")

            # 2.2 CALL TOOL: Get Status
            console.print(f"\n[cyan]Passo 3: Chamando Ferramenta 'get_workflow_status_tool' para [{workflow_id}]...[/cyan]")
            res_status = await session.call_tool(
                "get_workflow_status_tool", 
                {"db_path": db_path, "workflow_id": workflow_id}
            )
            console.print(f"[bold white]Resposta do Servidor:[/bold white] {res_status.content[0].text}")

            # 2.3 CALL TOOL: Execute Transition (PENDING -> READY)
            console.print("\n[cyan]Passo 4: Chamando Ferramenta 'transition_workflow_state_tool' via MCP (Ação: READY)...[/cyan]")
            res_trans = await session.call_tool(
                "transition_workflow_state_tool",
                {
                    "db_path": db_path,
                    "workflow_id": workflow_id,
                    "to_state": "READY",
                    "trigger_action": "MARK_READY",
                    "reason_metadata": "Dispatched by Antigravity Client Agent"
                }
            )
            console.print(f"[bold white]Resposta do Servidor:[/bold white] {res_trans.content[0].text}")

            # 2.4 READ RESOURCE: Read newly written ledger via URI Resource
            console.print("\n[cyan]Passo 5: Lendo Recurso 'lifeline://{db_path}/ledger' para auditar a transição...[/cyan]")
            resource_uri = f"lifeline://{db_path}/ledger"
            res_ledger = await session.read_resource(resource_uri)
            
            import json
            ledger_data = json.loads(res_ledger.contents[0].text)
            console.print("[dim white]Último evento auditado no ledger via Recurso MCP:[/dim white]")
            
            latest_ev = ledger_data["events"][0]
            console.print_json(data={
                "event_id": latest_ev["event_id"],
                "event_type": latest_ev["event_type"],
                "logical_clock": latest_ev["logical_clock"],
                "workflow_id": latest_ev["workflow_id"],
                "payload_action": latest_ev.get("payload", {}).get("action", "N/A"),
                "trigger": latest_ev.get("payload", {}).get("trigger", "N/A")
            })

            # 3. FINAL SANITY AUDIT
            assert latest_ev["event_type"] == "state_transition"
            assert latest_ev["payload"]["to_state"] == "READY"
            
            console.rule("[bold green]🏆 SUCESSO ABSOLUTO DE INTEGRAÇÃO END-TO-END! 🏆")
            console.print("[bold green]O Antigravity atuou como Cliente MCP, executou ferramentas e consumiu recursos de forma pura![/bold green]")

    # Cleanup physical DB
    if os.path.exists(db_name):
        try: os.remove(db_name)
        except: pass

if __name__ == "__main__":
    # Ensure proper loop context on Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run_antigravity_mcp_client())
