import asyncio
import os
from datetime import datetime
from lifeline.adapters.storage.sqlite import SQLiteEventStore, SQLiteSnapshotStore
from lifeline.bus.local_bus import LocalEventBus
from lifeline.engines.event_engine import EventEngine
from lifeline.engines.state_engine import StateEngine
from lifeline.engines.snapshot_engine import SnapshotEngine
from lifeline.sdk.client import LifelineClient
from lifeline.sdk.decorators import set_lifeline_context, trace_agent_step, trace_tool
from lifeline.core.events import WorkflowEvent
from lifeline.projections.markdown import MarkdownProjection

# 1. Define a mock agent system using lifeline decorators
@trace_agent_step(action_name="planning")
async def plan_task(objective: str):
    print(f"[Agent] Planning for: {objective}")
    await asyncio.sleep(0.1)
    return f"Plan: 1. Fetch data, 2. Process, 3. Report"

@trace_tool(tool_name="weather_api")
async def fetch_weather(location: str):
    print(f"[Tool] Fetching weather for {location}...")
    await asyncio.sleep(0.2)
    return {"temp": 22, "condition": "Cloudy"}

@trace_agent_step(action_name="reasoning")
async def reason_about_weather(plan: str, weather_data: dict):
    print("[Agent] Reasoning about optimal actions based on the plan and weather...")
    await asyncio.sleep(0.1)
    return f"Based on {weather_data['temp']} degrees C, we should proceed with standard indoor protocols."

# 2. Define a custom state reducer to build operational state
def workflow_state_reducer(state: dict, event) -> dict:
    if event.event_type == "workflow":
        state["current_status"] = event.status
        state["updated_at"] = event.timestamp.isoformat()
    elif event.event_type == "agent" and event.action == "planning":
        state["has_plan"] = True
        state["plan_summary"] = event.completion
    elif event.event_type == "tool_execution":
        if "tools_called" not in state:
            state["tools_called"] = []
        state["tools_called"].append(event.tool_name)
    return state

async def run_agent_simulation():
    db_path = "lifeline_demo.db"
    # Cleanup old demo database
    if os.path.exists(db_path):
        os.remove(db_path)

    print("--- Initializing Lifeline infrastructure ---")
    # 3. Wire the operational substrate
    event_store = SQLiteEventStore(db_path=db_path)
    snapshot_store = SQLiteSnapshotStore(db_path=db_path)
    
    await event_store.initialize()
    await snapshot_store.initialize()

    event_engine = EventEngine(event_store)
    state_engine = StateEngine(event_engine)
    
    # Register our state reducer
    state_engine.register_reducer("workflow", workflow_state_reducer)
    state_engine.register_reducer("agent", workflow_state_reducer)
    state_engine.register_reducer("tool_execution", workflow_state_reducer)
    
    snapshot_engine = SnapshotEngine(snapshot_store, state_engine, event_engine)
    bus = LocalEventBus()
    
    # Initialize high-level SDK Client
    client = LifelineClient(event_engine, state_engine, snapshot_engine, bus)
    await client.start()

    # 4. Set Execution Context
    workflow_id = "wf_alpha_99"
    agent_id = "agent_nexus_1"
    set_lifeline_context(client, workflow_id, agent_id)

    print(f"--- Executing Workflow: {workflow_id} ---")
    # Publish explicit workflow start event
    await client.publish(WorkflowEvent(
        workflow_id=workflow_id, 
        agent_id=agent_id, 
        status="started"
    ))

    # 5. Execute agent logic (decorators automatically emit causal events to the bus/store)
    objective = "Optimize solar panel direction for today's climate."
    plan = await plan_task(objective)
    weather = await fetch_weather("Araranguá")
    decision = await reason_about_weather(plan, weather)

    print(f"[Agent] Final Decision: {decision}")

    # Publish explicit workflow completion event
    await client.publish(WorkflowEvent(
        workflow_id=workflow_id, 
        agent_id=agent_id, 
        status="completed"
    ))

    print("\n--- Reconstructing State from Event Sourcing ---")
    final_state = await client.get_workflow_state(workflow_id)
    print(f"Reconstructed State: {final_state}")

    print("\n--- Projecting Markdown Representation ---")
    stream = event_engine.get_workflow_stream(workflow_id)
    markdown = await MarkdownProjection.generate_from_stream(stream, title=f"Nexus Agent Execution: {workflow_id}")
    
    with open("execution_trace.md", "w", encoding="utf-8") as f:
        f.write(markdown)
    print("Saved execution_trace.md!")

if __name__ == "__main__":
    asyncio.run(run_agent_simulation())
