import asyncio
import os
import sys
import sqlite3

from devos.swarm import DevOSSwarmOrchestrator
from lifeline.adapters.observability.profiler import kernel_profiler
from lifeline.engines.replay_engine import ReplayEngine
from lifeline.engines.event_engine import EventEngine

def generate_broken_workspace(branch_count: int):
    for i in range(1, branch_count + 1):
        suffix = chr(64 + i)
        with open(f"broken_module_{suffix}.py", "w") as f:
            f.write(f"def execute_core_computation(): raise AssertionError()\n")
        with open(f"test_broken_{suffix}.py", "w") as f:
            f.write(f"""import unittest
import broken_module_{suffix}
class TestBroken(unittest.TestCase):
    def test_c(self): self.assertEqual(broken_module_{suffix}.execute_core_computation(), 42)
""")

def cleanup_workspace(branch_count: int):
    for i in range(1, branch_count + 1):
        suffix = chr(64 + i)
        for f in [f"broken_module_{suffix}.py", f"test_broken_{suffix}.py"]:
            if os.path.exists(f): os.remove(f)

async def main():
    print("==================================================")
    print("   LIFELINE FLIGHT DASHBOARD & DRIFT ANALYSIS")
    print("==================================================\n")

    db_file = "simulation_flight_telemetry.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    # 1. Setup workspace
    branch_count = 3
    generate_broken_workspace(branch_count)
    fix_patch = "def execute_core_computation(): return 42\n"

    swarm = DevOSSwarmOrchestrator(db_file)
    await swarm.bootstrap()

    print("[SIM] Launching Concurrent Causal Workload with active Profiler Sensors...\n")
    
    try:
        # 2. Run stress storm
        await swarm.run_chaos_storm(
            workflow_id="wf_telemetry_01",
            fix_perm_content=fix_patch,
            branch_count=branch_count
        )
        
        # 3. RENDER SYSTEM FLIGHT DASHBOARD
        metrics = kernel_profiler.get_snapshot()
        
        print("\n" + "="*50)
        print("           LIFELINE OS FLIGHT DASHBOARD")
        print("="*50)
        print(f" -> Active Threads Managed: {metrics['active_processes']}")
        print(f" -> Scheduler Cycles:       {metrics['scheduler_ticks']} ticks")
        print(f" -> Avg Pending Depth:      {metrics['avg_pending_queue']} tasks")
        print(f" -> Avg Blocked Depth:      {metrics['avg_blocked_queue']} tasks")
        print(f" -> Cache Accuracy Ratio:   {metrics['cache_hit_ratio']}%")
        print(f" -> Cache Profiling:        [Hits: {metrics['cache_hits']} | Misses: {metrics['cache_misses']}]")
        print(f" -> Avg Context Assembly:   {metrics['avg_reconstruction_ms']} ms")
        print("="*50 + "\n")

        # 4. PHYSICAL DRIFT DETECTION - STAGE 1 (Sanity Audit)
        print("[AUDIT] Initiating Causal Integrity Verification on pristine Ledger...")
        replay_engine = ReplayEngine(swarm.event_engine)
        
        drifted, diag_msg = await replay_engine.verify_execution_drift("wf_telemetry_01")
        
        print(f" -> STATUS: {'[CRITICAL DRIFT]' if drifted else '[PRISTINE_LEDGER]'}")
        print(f" -> AUDIT DIAGNOSTIC: {diag_msg}\n")

        # 5. DRIFT FAULT INJECTION (Corrupting the persistent timeline)
        print("[ATTACK] Injecting Temporal Clock Corruption directly into physical storage...")
        
        # Manually corrupt an event clock in SQLite (both index and serialized JSON payload!)
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get the maximum logical clock event (typically the last tester execution)
        cursor.execute("SELECT event_id, logical_clock, payload FROM events WHERE workflow_id='wf_telemetry_01' ORDER BY logical_clock DESC LIMIT 1")
        row = cursor.fetchone()
        
        if row:
            target_id, old_clock, raw_payload = row
            print(f" -> Injecting corruption on Event '{target_id[:8]}' (Overwriting Clock {old_clock} -> 1)")
            
            # Inject corrupted payload string
            import json
            payload_dict = json.loads(raw_payload)
            payload_dict["logical_clock"] = 1
            corrupted_payload = json.dumps(payload_dict)
            
            # Overwrite column AND embedded payload to bypass Event Sourcing immutability
            cursor.execute("UPDATE events SET logical_clock = 1, payload = ? WHERE event_id = ?", (corrupted_payload, target_id))
            conn.commit()
            
        conn.close()
        print("[ATTACK] Corruption sealed. Memory partition tainted.\n")

        # 6. AUDIT COMPROMISED LEDGER - STAGE 2 (Assert Alert fires!)
        print("[AUDIT] Re-Scanning tainted Ledger stream...")
        
        # Force fresh audit (Rebuild engine to avoid cached memory objects)
        fresh_swarm = DevOSSwarmOrchestrator(db_file)
        await fresh_swarm.bootstrap()
        fresh_replay = ReplayEngine(fresh_swarm.event_engine)
        
        drifted_2, diag_msg_2 = await fresh_replay.verify_execution_drift("wf_telemetry_01")
        
        print(f" -> STATUS: {'[CRITICAL DRIFT]' if drifted_2 else '[PRISTINE_LEDGER]'}")
        print(f" -> AUDIT DIAGNOSTIC: {diag_msg_2}\n")
        
        if drifted_2:
            print("==================================================")
            print("     FLIGHT DASHBOARD VERIFICATION: PASS [SUCCESS]")
            print("   Sensors & Causal Guardrails fully operational!")
            print("==================================================")
        else:
            print("==================================================")
            print("     FLIGHT DASHBOARD VERIFICATION: FAIL [ERROR]")
            print("==================================================")

    finally:
        cleanup_workspace(branch_count)

if __name__ == "__main__":
    asyncio.run(main())
