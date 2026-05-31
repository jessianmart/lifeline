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

@app.command()
def init():
    """Initializes Lifeline configuration and .cursorrules in the current working directory."""
    import os
    console.print("[bold cyan]Initializing Lifeline OS in current directory...[/bold cyan]")
    
    cursorrules_content = """# INVARIANTES E REGRAS MATEMÁTICAS (MODO AX)

## 1. INVARIANTE DE INTEGRIDADE CAUSAL (DAG)
REGRA: O logical_clock de um evento filho deve ser estritamente superior ao maior logical_clock de todos os seus parent_event_ids.
Fórmula: clock_filho = max(clock_parents) + 1
IMPLICAÇÃO: Violar isto corrompe o DAG e causa falha crítica no EventEngine. Eventos são imutáveis e append-only.

## 2. MAPEAMENTO DA MÁQUINA DE ESTADOS (WorkflowStateMachine)
Dicionário exato de transições válidas (Qualquer desvio levanta StateReconstructionError):
```python
VALID_TRANSITIONS = {
    "PENDING": ["READY", "CANCELLED"],
    "READY": ["RUNNING", "CANCELLED"],
    "RUNNING": ["WAITING", "RETRYING", "COMPLETED", "FAILED", "TIMEOUT", "CANCELLED"],
    "WAITING": ["RUNNING", "TIMEOUT", "CANCELLED"],
    "RETRYING": ["RUNNING", "CANCELLED"],
    "COMPLETED": ["ROLLEDBACK"],
    "FAILED": ["RETRYING", "ROLLEDBACK"],
    "CANCELLED": ["ROLLEDBACK"],
    "TIMEOUT": ["RETRYING", "ROLLEDBACK"],
    "ROLLEDBACK": ["READY"]
}
```

## 3. TOPOLOGIA DE ESTADOS
```mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> READY
    READY --> RUNNING
    RUNNING --> WAITING
    RUNNING --> RETRYING
    RUNNING --> COMPLETED
    RUNNING --> FAILED
    RUNNING --> TIMEOUT
    WAITING --> RUNNING
    RETRYING --> RUNNING
    COMPLETED --> ROLLEDBACK
    FAILED --> ROLLEDBACK
    ROLLEDBACK --> READY
```

## 4. TAXONOMIA DE EXCEÇÕES COMO CONTROLO DE FLUXO
- `CognitiveParsingError`: ERRO DE LLM. CAPTURAR E EMITIR `FailureEvent(failure_domain="COGNITIVE", recovered=False)`. NÃO interromper a execução física. O compressor agrupará retries sequenciais automaticamente.
- `ResourceExhaustionError`: THROTTLING. Mover estado para `SUSPENDED_RATE_LIMIT` e suspender execução até o epoch permitido.

## 5. RIGIDEZ DE TIPAGEM (Pydantic Strict=True)
- Ativo em `EventBase`, `ScheduledTask`, `ProcessControlBlock`, `ContextBudget`, `ResourceQuota`.
- COERÇÃO PROIBIDA: Converter explicitamente datetimes ISO e strings numéricas antes de instanciar classes. 

## 6. DIRETRIZES DE AUTOCONFIGURAÇÃO DO ANTIGRAVITY (AGENTE CODER)

Como agente autônomo (Antigravity), você deve consumir as capacidades do próprio Lifeline SDK neste projeto para otimizar o seu runtime de contexto e execução:

1. **Uso de Sandbox para Execução Física**:
   - Sempre que precisar rodar testes unitários ou executar códigos temporários de teste, dê preferência a usar o `IsolatedSandboxExecutor` do Lifeline em Python para rodá-los isoladamente no contêiner Docker "warm", em vez de executá-los diretamente no host.
   - Isso garante proteção física contra loops infinitos de execução e efeitos colaterais.

2. **Criação de Contexto Persistente (Causal Ledger)**:
   - Para manter um histórico de raciocínio imutável e estruturado entre as sessões de chat, inicialize o `SQLiteEventStore` e grave eventos cognitivos (`AgentEvent`) e de ferramentas (`ToolExecutionEvent`) no banco de dados local.
   - Isso garante que a linhagem lógica de tomada de decisão não seja perdida quando a janela de contexto expirar.

3. **Geração de Projeções de Observabilidade (Markdown)**:
   - Ao finalizar tarefas complexas ou loops de depuração, consuma o fluxo de eventos gravados e use a classe `MarkdownProjection` para gerar relatórios detalhados (`execution_trace.md`), fornecendo observabilidade instantânea para o usuário.
"""

    target_path = os.path.join(os.getcwd(), ".cursorrules")
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(cursorrules_content)
        console.print(f"[bold green]Successfully initialized .cursorrules at:[/bold green] {target_path}")
    except Exception as e:
        console.print(f"[bold red]Failed to write .cursorrules: {e}[/bold red]")

if __name__ == "__main__":
    app()
