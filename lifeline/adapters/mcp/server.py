import sqlite3
import json
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

# Instantiate Model Context Protocol hub for LLM Coders/Agents
mcp = FastMCP("Lifeline Cognitive Microkernel")

@mcp.resource("lifeline://{db_path}/ledger")
def inspect_causal_ledger(db_path: str) -> str:
    """
    MCP Resource exposing the raw immutable causal ledger (events) recorded in SQLite.
    Allows LLM agents to inspect past transactions and replay logical clocks.
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM causal_ledger ORDER BY logical_clock DESC LIMIT 100")
        rows = cursor.fetchall()
        conn.close()
        
        events = []
        for row in rows:
            ev = dict(row)
            # Expand dynamic payload column if valid json
            if "payload" in ev and ev["payload"]:
                try: ev["payload"] = json.loads(ev["payload"])
                except: pass
            events.append(ev)
            
        return json.dumps({
            "status": "SUCCESS",
            "database": db_path,
            "record_count": len(events),
            "events": events
        }, indent=2, default=str)
    except Exception as exc:
        return json.dumps({
            "status": "ERROR",
            "reason": f"Failed reading ledger: {str(exc)}"
        }, indent=2)

@mcp.resource("lifeline://{db_path}/dead_letters")
def inspect_dlq(db_path: str) -> str:
    """
    MCP Resource exposing the captured isolated Failures in the DLQ system.
    Allows LLM agents to evaluate execution traces and formulate contextual remedies.
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dead_letters ORDER BY failed_at DESC LIMIT 50")
        rows = cursor.fetchall()
        conn.close()
        
        records = []
        for row in rows:
            rec = dict(row)
            if "event_payload" in rec and rec["event_payload"]:
                try: rec["event_payload"] = json.loads(rec["event_payload"])
                except: pass
            records.append(rec)
            
        return json.dumps({
            "status": "SUCCESS",
            "database": db_path,
            "dlq_count": len(records),
            "records": records
        }, indent=2, default=str)
    except Exception as exc:
        return json.dumps({
            "status": "ERROR",
            "reason": f"Failed reading DLQ: {str(exc)}"
        }, indent=2)

@mcp.tool()
async def get_workflow_status_tool(db_path: str, workflow_id: str) -> str:
    """
    Retrieves the current validated State of a Workflow Machine by replaying transitions.
    """
    from lifeline.adapters.storage.sqlite import SQLiteEventStore
    from lifeline.engines.event_engine import EventEngine
    from lifeline.runtime.state_machine import WorkflowStateMachine
    
    try:
        store = SQLiteEventStore(db_path)
        await store.initialize()
        engine = EventEngine(store)
        sm = WorkflowStateMachine(engine)
        
        current_state = await sm.get_current_state(workflow_id)
        return f"WORKFLOW '{workflow_id}' CURRENT STATE: '{current_state}'"
    except Exception as e:
        return f"ERROR: Failed retrieving state machine status. Reason: {str(e)}"

@mcp.tool()
async def transition_workflow_state_tool(
    db_path: str,
    workflow_id: str,
    to_state: str,
    trigger_action: str,
    reason_metadata: Optional[str] = None
) -> str:
    """
    Executes a valid physical state machine transition on a targeting Workflow.
    Guaranteed transactional write to the Causal Ledger.
    """
    from lifeline.adapters.storage.sqlite import SQLiteEventStore
    from lifeline.engines.event_engine import EventEngine
    from lifeline.runtime.state_machine import WorkflowStateMachine
    
    try:
        store = SQLiteEventStore(db_path)
        await store.initialize()
        engine = EventEngine(store)
        sm = WorkflowStateMachine(engine)
        
        meta = {"reason": reason_metadata} if reason_metadata else {}
        
        # Trigger state change
        ev = await sm.transition(
            workflow_id=workflow_id,
            to_state=to_state, # type: ignore
            trigger=trigger_action,
            metadata=meta,
            agent_id="MCP_ADMIN_AGENT"
        )
        
        return (
            f"TRANSITION SUCCESS: Workflow '{workflow_id}' moved from '{ev.from_state}' to '{ev.to_state}'. "
            f"Event Sealed ID: {ev.event_id}"
        )
    except Exception as e:
        return f"TRANSITION HALTED: {str(e)}"

if __name__ == "__main__":
    # When run directly, launch the FastMCP server (handles Stdio transport by default)
    mcp.run()
