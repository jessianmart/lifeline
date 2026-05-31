# Lifeline SDK: Cognitive Microkernel & Event-Driven OS Substrate 🪐☄️🛰️

O Lifeline é um microkernel cognitivo orientado a eventos, projetado para preservar causalidade, estado determinístico, reasoning e continuidade operacional de sistemas agênticos avançados.

Diferente de um mero framework de logs, o Lifeline opera sob o paradigma rigoroso de **Event Sourcing** (DAG com Relógios de Lamport), isolamento físico (Docker Warm Pools) e integração transparente via **Model Context Protocol (MCP)**.

---

## 🏗️ Pilares Arquiteturais

1.  **Core Microkernel**: Livro-razão imutável (ledger) em SQLite com WAL blindado contra bloqueios concorrentes.
2.  **Physical Sandbox**: Execução segura em containers efêmeros pré-aquecidos (<50ms latência) com limitação estrita de cgroups e rede.
3.  **Distributed Portability**: Replicação binária compactada (zlib) de checkpoints e suporte ao padrão Claim Check.
4.  **AI Workspace Integration**: Ponte bidirecional MCP para expor o estado real e logs DLQ para o Cursor IDE ou Claude Desktop.

---

## ⚙️ Instalação Rápida (Quickstart)

Para instalar o Lifeline localmente em modo editável dentro do seu novo projeto:

```bash
# Acesse o repositório e execute:
pip install -e .
```

---

## 💻 Uso no Código (Maturidade DX/AX)

O SDK expõe fachadas limpas na raiz para rápida inicialização de agentes:

```python
import asyncio
from lifeline import SQLiteEventStore, EventEngine, WorkflowStateMachine, IsolatedSandboxExecutor, ResourceManager

async def main():
    # 1. Inicializar a Fundação de Persistência
    store = SQLiteEventStore("lifeline_prod.db")
    await store.initialize()
    
    # 2. Acionar os Motores Cognitivos
    engine = EventEngine(store)
    state_machine = WorkflowStateMachine(engine)
    
    # 3. Executar uma transição formal rastreável no DAG
    workflow_id = "workflow_agent_001"
    await state_machine.transition(
        workflow_id=workflow_id,
        to_state="RUNNING",
        trigger_action="BOOT_MAIN_GOAL",
        agent_id="primary_reasoner"
    )
    
    # 4. Despachar Sandbox Físico (Opcional)
    res_mgr = ResourceManager()
    sandbox = IsolatedSandboxExecutor(res_mgr, unsafe_allow_host_execution=True)
    result, telemetry = await sandbox.execute_physical_command("primary_reasoner", ["python", "-c", "print('Executando código isolado')"])
    print("Status da Execução:", telemetry.success)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🔌 Ativando o MCP no Cursor ou Claude Desktop

Exponha o seu banco de dados físico para a inteligência da IDE auditar em tempo real:

```bash
# Comando para registrar no campo 'MCP Server command':
python <CAMINHO_ATÉ_O_SDK>/lifeline/adapters/mcp/server.py
```

### Recursos MCP Expostos:
*   `lifeline://{db_path}/ledger`: Replay total dos 100 últimos eventos imutáveis.
*   `lifeline://{db_path}/dead_letters`: Auditoria de exceções, falhas cognitivas e rastros de erros.

---

## 🛡️ Engenharia de Resiliência e Caos
O Lifeline é testado sob o pior cenário de infraestrutura física. Para executar a suite de simulação de partição de rede real (Split-Brain) e validar as colisões de chaves únicas:

```bash
$env:PYTHONPATH="."
python verify_split_brain_storm.py
```
