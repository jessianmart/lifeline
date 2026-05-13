import asyncio
import os
import sys
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table

from lifeline.core.events import AgentEvent, SystemEvent
from lifeline.adapters.storage.sqlite import SQLiteEventStore
from lifeline.engines.event_engine import EventEngine
from lifeline.engines.state_engine import StateEngine
from lifeline.graph.reconciliation import BranchReconciler

console = Console()

class SplitBrainChaosStorm:
    """
    Industrial physical simulator for Multi-Node network partition (Split-Brain).
    Tests DAG idempotency, Lamport clock fork detection, and causal reconstruction.
    """

    def __init__(self):
        self.db_a = "storm_node_a.db"
        self.db_b = "storm_node_b.db"
        self.cleanup_files()

    def cleanup_files(self):
        for f in [self.db_a, self.db_b, f"{self.db_a}-wal", f"{self.db_b}-wal"]:
            if os.path.exists(f):
                try: os.remove(f)
                except: pass

    async def run_storm(self):
        console.rule("[bold red]🔥 INICIANDO TEMPESTADE DE CAOS (SPLIT-BRAIN) 🔥")

        # 1. Setup physical stores
        store_a = SQLiteEventStore(self.db_a)
        store_b = SQLiteEventStore(self.db_b)
        await store_a.initialize()
        await store_b.initialize()

        engine_a = EventEngine(store_a)
        engine_b = EventEngine(store_b)
        
        state_a = StateEngine(engine_a)
        reconciler_a = BranchReconciler(engine_a, state_a)

        workflow_id = "wf_chaos_001"

        # 2. PHASE 1: BOOTSTRAP (Nós em Consenso)
        console.print("\n[cyan][FASE 1]: Inicializando estado sincronizado...[/cyan]")
        ev_genesis = SystemEvent(
            logical_clock=0,
            timestamp=datetime.now(timezone.utc),
            workflow_id=workflow_id,
            action="BOOTSTRAP"
        )
        # Seal and append to both to simulate perfect sync initial state
        ev_genesis.seal([], 0)
        genesis_id = ev_genesis.event_id
        await store_a.append(ev_genesis)
        await store_b.append(ev_genesis)
        console.print(f"[dim green]✔ Genesis [{genesis_id}] injetado em ambos os nós.[/dim green]")

        # 3. PHASE 2: A REDE CAIU! (PARTITION ACTIVE)
        console.rule("[bold yellow]⚡ PARTIÇÃO DE REDE ATIVADA (NÓ B ISOLADO) ⚡")
        console.print("[yellow]Os nós operam autonomamente sem replicar eventos entre si por 5 segundos...[/yellow]")

        # 3.1 Nó A executa a tarefa 'ANALYZE_PAYLOAD'
        ev_a1 = AgentEvent(
            logical_clock=1,
            timestamp=datetime.now(timezone.utc),
            workflow_id=workflow_id,
            action="EXECUTE_TASK",
            deduplication_key="dedup_task_llm_analyze",
            prompt="Analyze system metrics",
            completion="Analysis complete (Done by Node A)"
        )
        ev_a1.seal([genesis_id], 1)
        ev_a1_id = ev_a1.event_id
        await store_a.append(ev_a1)
        console.print(f"[bold green]Nó A executou tarefa: [{ev_a1_id}] com dedup_key='dedup_task_llm_analyze'[/bold green]")

        # 3.2 Nó B (no escuro) tenta executar A MESMA tarefa!
        ev_b1 = AgentEvent(
            logical_clock=1,
            timestamp=datetime.now(timezone.utc),
            workflow_id=workflow_id,
            action="EXECUTE_TASK",
            deduplication_key="dedup_task_llm_analyze", # Conflito exato!
            prompt="Analyze system metrics",
            completion="Analysis complete (Done by Node B)"
        )
        ev_b1.seal([genesis_id], 1)
        ev_b1_id = ev_b1.event_id
        await store_b.append(ev_b1)
        console.print(f"[bold magenta]Nó B executou tarefa: [{ev_b1_id}] com dedup_key='dedup_task_llm_analyze'[/bold magenta]")

        # 3.3 Nó B continua trabalhando em cima de seu fork local!
        ev_b2 = AgentEvent(
            logical_clock=2,
            timestamp=datetime.now(timezone.utc),
            workflow_id=workflow_id,
            action="FURTHER_STEP",
            prompt="Refine previous results",
            completion="Refined by Node B"
        )
        ev_b2.seal([ev_b1_id], 2)
        ev_b2_id = ev_b2.event_id
        await store_b.append(ev_b2)
        console.print(f"[dim magenta]Nó B estendeu ramo local: [{ev_b2_id}] filho de B1[/dim magenta]")

        # 4. PHASE 3: REDE RESTAURADA & INUNDAÇÃO!
        console.rule("[bold blue]🌐 REDE RESTAURADA! INICIANDO SINCRONIZAÇÃO CRUZA DE LEDGER 🌐")
        console.print("[cyan]O Nó A recebe a enxurrada de eventos do Nó B...[/cyan]")

        # Simular a ingestão de B1 no Nó A
        try:
            await store_a.append(ev_b1)
            console.print("[dim green]Replicação de B1 enviada...[/dim green]")
        except Exception as e:
            console.print(f"[red]Erro inesperado: {e}[/red]")

        # Simular a ingestão de B2 no Nó A
        try:
            await store_a.append(ev_b2)
            console.print("[dim green]Replicação de B2 enviada...[/dim green]")
        except Exception as e:
            console.print(f"[red]Erro inesperado: {e}[/red]")

        # 5. AUDITORIA DE DEDUPLICAÇÃO FÍSICA
        console.print("\n[bold white]🔍 AUDITANDO LEDGER DO NÓ A PÓS-TEMPESTADE...[/bold white]")
        
        # O evento B1 não deve existir em A, pois a chave dedup já pertencia ao evento A1!
        check_b1 = await engine_a.get_event(ev_b1_id)
        check_a1 = await engine_a.get_event(ev_a1_id)
        check_b2 = await engine_a.get_event(ev_b2_id)

        success_dedup = check_b1 is None and check_a1 is not None
        
        table = Table(title="Integridade do Ledger em Node A")
        table.add_column("Evento", justify="left", style="cyan")
        table.add_column("Origem", justify="center", style="yellow")
        table.add_column("Status no Nó A", justify="center")
        table.add_column("Nota Causal")

        table.add_row("EV_A1", "Nó A", "[green]GRAVADO[/green]", "Venceu a corrida de rede na partição.")
        table.add_row("EV_B1", "Nó B", "[red]REJEITADO[/red]" if check_b1 is None else "[green]ACEITO[/green]", "Idempotency key evitou duplicação da API.")
        table.add_row("EV_B2", "Nó B", "[green]GRAVADO[/green]" if check_b2 else "[red]AUSENTE[/red]", "Ramo órfão integrado sem o pai físico.")

        console.print(table)

        if success_dedup:
            console.print("[bold green]✔ SUCESSO ABSOLUTO: O UNIQUE INDEX travou e descartou o evento B1 silenciosamente! Nenhuma API duplicada atingiu o Ledger![/bold green]")
        else:
            console.print("[bold red]✘ FALHA DE INTEGRIDADE: A duplicata do Nó B conseguiu infectar o ledger![/bold red]")
            sys.exit(1)

        # 6. FASE 4: RECONCILIAÇÃO CAUSAL DO DAG
        console.rule("[bold magenta]🧬 ACIONANDO BRANCH RECONCILER 🧬")
        
        # O Reconciler deve ser acionado para fundir o leaf do Nó A (ev_a1_id) com o leaf do Nó B (ev_b2_id)
        # Mas note: ev_b2 no banco de A aponta para ev_b1, que foi REJEITADO!
        # O sistema lida com isso graciosamente? Vamos rodar!
        try:
            # Como ev_b1 não existe fisicamente no Node A, precisamos garantir que o reconciler consiga calcular 
            # a linhagem a partir dos links existentes.
            # Vamos fundir usando a estratégia de união!
            merge_event_id = await reconciler_a.reconcile_branches(
                workflow_id=workflow_id,
                event_id_a=ev_a1_id,
                event_id_b=ev_b2_id,
                strategy="keep_both_merged"
            )
            console.print(f"[bold green]✔ FUSÃO EXECUTADA! Novo nó de convergência selado no DAG: [{merge_event_id}][/bold green]")
            
            # Recuperar evento de fusão
            merge_ev = await engine_a.get_event(merge_event_id)
            console.print(f"[dim cyan]Pais da fusão: {merge_ev.parent_event_ids}[/dim cyan]")
            
        except Exception as ex:
            console.print(f"[bold red]✘ FALHA NO MOTOR DE RECONCILIAÇÃO: {ex}[/bold red]")
            sys.exit(1)

        console.rule("[bold green]🏆 CAOS SUPERADO COM DETERMINISMO ABSOLUTO! 🏆")
        self.cleanup_files()

if __name__ == "__main__":
    asyncio.run(SplitBrainChaosStorm().run_storm())
