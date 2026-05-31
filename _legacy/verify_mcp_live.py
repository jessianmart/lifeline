import asyncio
import os
import json
from datetime import datetime, timezone
from rich.console import Console

from lifeline.core.events import SystemEvent
from lifeline.adapters.storage.sqlite import SQLiteEventStore
from lifeline.adapters.mcp.server import inspect_causal_ledger, inspect_dlq

console = Console()

async def test_mcp_live_execution():
    console.rule("[bold cyan]📡 INICIANDO TESTE DE USO FÍSICO MCP 📡")
    
    db_path = "verify_mcp_live.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    # 1. Pre-populate a physical SQLite database with authentic events
    console.print("[yellow]Passo 1: Populando banco de dados temporário...[/yellow]")
    store = SQLiteEventStore(db_path)
    await store.initialize()
    
    ev = SystemEvent(
        logical_clock=1,
        timestamp=datetime.now(timezone.utc),
        workflow_id="wf_mcp_test",
        action="BOOTSTRAP",
        execution_metadata={"client": "mcp_tester"}
    )
    ev.seal([], 1)
    await store.append(ev)
    console.print(f"[green]✔ Evento [{ev.event_id}] gravado com sucesso.[/green]")

    # 2. Physically Invoke MCP Resource
    console.print("\n[yellow]Passo 2: Chamando Recurso MCP 'lifeline://{db_path}/ledger'...[/yellow]")
    
    # Invoke underlying python function mapping to the MCP route!
    # This validates URI ro parsing and dynamic JSON stringifying
    response_json = inspect_causal_ledger(db_path)
    
    # 3. Validate response structure
    try:
        data = json.loads(response_json)
        console.print("\n[bold green]✔ RESPOSTA RECEBIDA E DESERIALIZADA:[/bold green]")
        console.print_json(data=data)
        
        assert data["status"] == "SUCCESS"
        assert data["record_count"] == 1
        assert data["events"][0]["event_id"] == ev.event_id
        
        console.print("\n[bold green]🏆 SUCESSO TOTAL: O MCP leu a base física via URI mode=ro perfeitamente! 🏆[/bold green]")
    except Exception as ex:
        console.print(f"\n[bold red]✘ FALHA NA VALIDAÇÃO DO MCP: {ex}[/bold red]")
        raise ex
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)

if __name__ == "__main__":
    asyncio.run(test_mcp_live_execution())
