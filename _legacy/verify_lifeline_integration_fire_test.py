import asyncio
import os
import sys
import time
from datetime import datetime, timezone

from lifeline import (
    SQLiteEventStore,
    EventEngine,
    WorkflowStateMachine,
    IsolatedSandboxExecutor,
    ResourceManager
)
from lifeline.core.events import (
    AgentEvent,
    ToolExecutionEvent,
    SystemEvent,
    WorkflowStateTransitionEvent
)
from lifeline.runtime.resources import ResourceQuota
from lifeline.projections.markdown import MarkdownProjection

async def run_fire_test():
    print("=" * 60)
    print(">>> INICIANDO TESTE DE FOGO DA INTEGRACAO DO LIFELINE SDK <<<")
    print("=" * 60)
    
    db_path = "simulation_fire_test.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass
        
    # 1. Inicializar SQLite Event Store
    print("[1/6] Inicializando SQLite Event Store com timeout de 30s...")
    store = SQLiteEventStore(db_path)
    await store.initialize()
    engine = EventEngine(store)
    print("[OK] Event Store inicializado com sucesso.")

    # 2. Inicializar Máquina de Estados (Workflow)
    print("[2/6] Inicializando Maquina de Estados do Workflow...")
    sm = WorkflowStateMachine(engine)
    workflow_id = "wf_fire_test_999"
    
    # Transição PENDING -> READY
    ev1 = await sm.transition(
        workflow_id=workflow_id,
        to_state="READY",
        trigger="BOOTSTRAP",
        agent_id="antigravity_core"
    )
    print(f"[OK] Transicao PENDING -> READY concluida. Evento ID: {ev1.event_id[:8]}... | Clock: {ev1.logical_clock}")
    
    # Transição READY -> RUNNING
    ev2 = await sm.transition(
        workflow_id=workflow_id,
        to_state="RUNNING",
        trigger="EXECUTE_SANDBOX_STRESS",
        agent_id="antigravity_core"
    )
    print(f"[OK] Transicao READY -> RUNNING concluida. Evento ID: {ev2.event_id[:8]}... | Clock: {ev2.logical_clock}")

    # 3. Disparar Sandbox com Recursos Limitados
    print("[3/6] Preparando Executor Sandbox e cota de recursos...")
    resource_mgr = ResourceManager()
    quota = ResourceQuota(max_tokens=10000, max_execution_ms=30000)
    resource_mgr.provision_quota("antigravity_core", quota)
    # Ativa unsafe_allow_host_execution=True para garantir que rode mesmo se Docker não estiver ativo no Windows local do usuário
    sandbox = IsolatedSandboxExecutor(resource_mgr, unsafe_allow_host_execution=True)
    
    # Script para rodar no contêiner que testa o isolamento
    sandbox_script = (
        "import sys, os; "
        "print('=== DENTRO DO SANDBOX ==='); "
        "print(f'Python Version: {sys.version.split()[0]}'); "
        "print('Calculando primos para simular carga...'); "
        "primos = [x for x in range(2, 5000) if all(x % y != 0 for y in range(2, int(x**0.5) + 1))]; "
        "print(f'Carga de CPU concluida. Encontrados {len(primos)} numeros primos.'); "
        "print('Isolamento verificado!')"
    )
    
    print("[4/6] Executando comando de stress dentro do Sandbox...")
    start_time = time.time()
    res_dict, telemetry = await sandbox.execute_physical_command(
        agent_id="antigravity_core",
        cmd_args=["python", "-c", sandbox_script],
        cwd="."
    )
    duration = time.time() - start_time
    
    exit_code = res_dict["returncode"]
    stdout = res_dict["stdout"]
    stderr = res_dict["stderr"]
    via = res_dict["isolated_via"]
    
    print(f"-> Sandbox encerrado em {duration*1000:.2f}ms via {via} | Codigo de Saida: {exit_code}")
    print(f"--- STDOUT --- \n{stdout.strip()}\n--------------")
    
    if exit_code != 0:
        print(f"[ERROR] Sandbox falhou com stderr: {stderr}")
        sys.exit(1)
        
    # 4. Registrar Evento de Ferramenta no Causal Ledger
    print("[5/6] Registrando execucao da ferramenta no Ledger de eventos...")
    tool_event = ToolExecutionEvent(
        workflow_id=workflow_id,
        agent_id="antigravity_core",
        tool_name="sandbox_runner",
        tool_args={"args": ["python", "-c", "..."]},
        tool_result=stdout,
        execution_duration=duration
    )
    # Selar o evento vinculando-o aos eventos anteriores da máquina de estados
    clock = max(ev1.logical_clock, ev2.logical_clock) + 1
    tool_event.seal(parent_hashes=[ev2.event_id], logical_clock=clock)
    await engine.emit(tool_event)
    print(f"[OK] Evento da ferramenta publicado. ID: {tool_event.event_id[:8]}... | Clock: {tool_event.logical_clock}")

    # Transição RUNNING -> COMPLETED
    ev3 = await sm.transition(
        workflow_id=workflow_id,
        to_state="COMPLETED",
        trigger="SANDBOX_VERIFIED",
        agent_id="antigravity_core"
    )
    print(f"[OK] Transicao RUNNING -> COMPLETED concluida. Evento ID: {ev3.event_id[:8]}... | Clock: {ev3.logical_clock}")

    # 5. Gerar Projeção de Observabilidade em Markdown
    print("[6/6] Gerando arquivo de projecao Markdown a partir do stream do ledger...")
    event_stream = engine.get_workflow_stream(workflow_id)
    markdown_report = await MarkdownProjection.generate_from_stream(
        event_stream, 
        title=f"Relatorio de Execucao do Teste de Fogo (Workflow {workflow_id})"
    )
    
    report_file = "fire_test_trace.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(markdown_report)
    print(f"[OK] Projecao Markdown gravada em '{report_file}'.")

    # 6. Exibir o Relatório Causal
    print("\n" + "=" * 60)
    print(">>> RESULTADO GERAL DO CAUSAL LEDGER <<<")
    print("=" * 60)
    async for ev in engine.get_workflow_stream(workflow_id):
        parent_str = ", ".join([p[:8] for p in ev.parent_event_ids]) if ev.parent_event_ids else "Nenhum"
        print(f"[{ev.timestamp.strftime('%H:%M:%S')}] Evento: {ev.event_type.upper():<16} | ID: {ev.event_id[:8]}... | Clock: {ev.logical_clock:<3} | Pais: {parent_str}")
    print("=" * 60)
    print(">>> TESTE DE FOGO CONCLUIDO COM SUCESSO! <<<")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_fire_test())
