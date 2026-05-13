import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from lifeline.adapters.storage.sqlite import SQLiteEventStore
from lifeline.engines.event_engine import EventEngine
from lifeline.projections.markdown import MarkdownProjection

app = typer.Typer(help="Lifeline Cognitive Microkernel CLI")
console = Console()

async def _list_workflow_events(db: str, workflow_id: str):
    store = SQLiteEventStore(db_path=db)
    engine = EventEngine(store)
    
    console.print(f"[bold green]Fetching events for workflow:[/bold green] {workflow_id}")
    
    table = Table(title=f"Workflow Events: {workflow_id}")
    table.add_column("Timestamp", style="cyan")
    table.add_column("Event ID", style="dim")
    table.add_column("Type", style="magenta")
    table.add_column("Action/Status", style="yellow")
    
    async for event in engine.get_workflow_stream(workflow_id):
        event_type = getattr(event, 'event_type', 'unknown')
        detail = ""
        if hasattr(event, 'action'):
            detail = event.action
        elif hasattr(event, 'status'):
            detail = event.status
        elif hasattr(event, 'tool_name'):
            detail = event.tool_name
            
        table.add_row(
            event.timestamp.strftime("%H:%M:%S"),
            event.event_id[:8],
            event_type,
            detail
        )
    console.print(table)

async def _generate_md(db: str, workflow_id: str, output: str):
    store = SQLiteEventStore(db_path=db)
    engine = EventEngine(store)
    
    stream = engine.get_workflow_stream(workflow_id)
    md = await MarkdownProjection.generate_from_stream(stream, title=f"Trace for {workflow_id}")
    
    with open(output, "w", encoding="utf-8") as f:
        f.write(md)
    console.print(f"[bold green]Markdown trace written to:[/bold green] {output}")

@app.command()
def events(
    workflow_id: str = typer.Argument(..., help="The workflow ID to trace"),
    db: str = typer.Option("lifeline_dev.db", help="Path to SQLite database")
):
    """Lists all events for a specified workflow."""
    asyncio.run(_list_workflow_events(db, workflow_id))

@app.command()
def export(
    workflow_id: str = typer.Argument(..., help="The workflow ID to trace"),
    output: str = typer.Option("trace.md", help="Output Markdown path"),
    db: str = typer.Option("lifeline_dev.db", help="Path to SQLite database")
):
    """Exports an execution trace projection to Markdown."""
    asyncio.run(_generate_md(db, workflow_id, output))

if __name__ == "__main__":
    app()
