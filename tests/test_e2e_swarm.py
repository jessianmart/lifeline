import unittest
import asyncio
import os
import sys
import sqlite3
import json
from unittest.mock import patch

from devos.swarm import DevOSSwarmOrchestrator
from lifeline.engines.replay_engine import ReplayEngine
from lifeline.adapters.observability.profiler import kernel_profiler
from lifeline.runtime.resources import ResourceQuota
from lifeline.core.exceptions import ExecutionPolicyError
from lifeline.bus.local_bus import LocalEventBus
from lifeline.core.events import SystemEvent
from lifeline.adapters.storage.sqlite import SQLiteEventStore
from lifeline.engines.redrive_engine import RedriveEngine

class TestLifelineE2E(unittest.IsolatedAsyncioTestCase):
    """
    Hardened Production E2E Test Suite for Lifeline Cognitive Hypervisor.
    
    # [AX RAG DIRECTIVE]: Este ficheiro serve como a documentação primária de consumo do SDK.
    # [INVARIANTE DE INSTANCIAÇÃO]: O DevOSSwarmOrchestrator demonstra a injeção de dependências obrigatória.
    # [INVARIANTE DE CONTROLO]: As barreiras causais e quarentenas do escalonador baseiam-se em 'depends_on_nodes'.
    
    Verifica:
    - WAL Mode & Fail-Fast storage
    - Dead Letter Queue persistence
    - Mandatory Container Sandboxing / Policy Error checks
    - Causal Concurrency Integrity
    """
    
    def setUp(self):
        self.db_file = f"test_e2e_run_{self.id().split('.')[-1]}.db"
        self.branch_files = []

    def tearDown(self):
        # Purge dynamic database
        if os.path.exists(self.db_file):
            try:
                os.remove(self.db_file)
                # Remove WAL files left by SQLite
                if os.path.exists(self.db_file + "-wal"): os.remove(self.db_file + "-wal")
                if os.path.exists(self.db_file + "-shm"): os.remove(self.db_file + "-shm")
            except Exception:
                pass
        
        # Purge dynamic workspace artifacts
        for f in self.branch_files:
            if os.path.exists(f):
                os.remove(f)

    def _generate_workspace(self, branches: list[str]):
        """Seeds dynamic python files for standard unittest subprocess isolation."""
        for suffix in branches:
            m_path = f"broken_module_{suffix}.py"
            t_path = f"test_broken_{suffix}.py"
            
            with open(m_path, "w") as f:
                f.write("def execute_core_computation(): raise AssertionError('E2E Seed Failure')\n")
            with open(t_path, "w") as f:
                f.write(f"""import unittest
import broken_module_{suffix}
class TestBroken(unittest.TestCase):
    def test_one(self): self.assertEqual(broken_module_{suffix}.execute_core_computation(), 42)
""")
            self.branch_files.extend([m_path, t_path])

    async def test_01_single_branch_self_repair(self):
        """E2E: Single-agent autonomous lifecycle (Bootstrap -> Patch -> Sandboxed Test -> Success)"""
        self._generate_workspace(["A"])
        
        # Opt-in to host execution because test running environment might not support Docker daemon
        swarm = DevOSSwarmOrchestrator(self.db_file, unsafe_allow_host_execution=True)
        await swarm.bootstrap()
        
        fix_patch = "def execute_core_computation(): return 42\n"
        
        passed = await swarm.run_chaos_storm(
            workflow_id="wf_e2e_01",
            fix_perm_content=fix_patch,
            branch_count=1
        )
        
        self.assertTrue(passed, "E2E Swarm failed to autonomously repair the single-branch module.")

    async def test_02_concurrency_storm_integrity(self):
        """E2E: Parallel fork bomb (3 concurrent workers, asyncio.gather)"""
        self._generate_workspace(["A", "B", "C"])
        
        swarm = DevOSSwarmOrchestrator(self.db_file, unsafe_allow_host_execution=True)
        await swarm.bootstrap()
        
        fix_patch = "def execute_core_computation(): return 42\n"
        
        passed = await swarm.run_chaos_storm(
            workflow_id="wf_e2e_02",
            fix_perm_content=fix_patch,
            branch_count=3
        )
        
        self.assertTrue(passed, "E2E Concurrency Storm failed with 3 concurrent branches.")

    async def test_03_drift_fault_detection(self):
        """E2E: Drift validation scanner asserts true on physical database corruption injection."""
        self._generate_workspace(["A"])
        
        swarm = DevOSSwarmOrchestrator(self.db_file, unsafe_allow_host_execution=True)
        await swarm.bootstrap()
        
        fix_patch = "def execute_core_computation(): return 42\n"
        await swarm.run_chaos_storm(
            workflow_id="wf_e2e_03",
            fix_perm_content=fix_patch,
            branch_count=1
        )
        
        # Inject drift attack directly in SQLite
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT event_id, logical_clock, payload FROM events ORDER BY logical_clock DESC LIMIT 1")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        
        target_id, _, raw_payload = row
        payload_dict = json.loads(raw_payload)
        payload_dict["logical_clock"] = 1 # Violate Monotonic Clock
        
        cursor.execute(
            "UPDATE events SET logical_clock = 1, payload = ? WHERE event_id = ?",
            (json.dumps(payload_dict), target_id)
        )
        conn.commit()
        conn.close()
        
        fresh_swarm = DevOSSwarmOrchestrator(self.db_file, unsafe_allow_host_execution=True)
        await fresh_swarm.bootstrap()
        replay_engine = ReplayEngine(fresh_swarm.event_engine)
        
        drifted, diag_msg = await replay_engine.verify_execution_drift("wf_e2e_03")
        
        self.assertTrue(drifted)
        self.assertIn("CLOCK DRIFT DETECTED", diag_msg)

    async def test_04_telemetry_profiling_data(self):
        """E2E: SystemicProfiler collects accurate non-zero measurements."""
        self._generate_workspace(["A"])
        swarm = DevOSSwarmOrchestrator(self.db_file, unsafe_allow_host_execution=True)
        await swarm.bootstrap()
        
        await swarm.run_chaos_storm(
            workflow_id="wf_e2e_04",
            fix_perm_content="def execute_core_computation(): return 42\n",
            branch_count=1
        )
        
        metrics = kernel_profiler.get_snapshot()
        self.assertGreater(metrics["scheduler_ticks"], 0)
        self.assertGreater(metrics["avg_reconstruction_ms"], 0.0)

    async def test_05_sandbox_policy_refusal_without_opt_in(self):
        """E2E: Asserts hard security refusal (ExecutionPolicyError) when container is missing and no opt-in is given."""
        self._generate_workspace(["A"])
        
        # DEFAULT STATE: unsafe_allow_host_execution = False
        swarm = DevOSSwarmOrchestrator(self.db_file, unsafe_allow_host_execution=False)
        await swarm.bootstrap()
        
        # Force simulate container daemon DOWN
        with patch.object(swarm.sandbox, "_check_docker_available", return_value=False):
            with self.assertRaises(ExecutionPolicyError) as context:
                await swarm.run_chaos_storm(
                    workflow_id="wf_e2e_05",
                    fix_perm_content="def execute_core_computation(): return 42\n",
                    branch_count=1
                )
            
            self.assertIn("CRITICAL SECURITY DENIAL", str(context.exception))

    async def test_06_dead_letter_queue_recording(self):
        """E2E: Verify that downstream processing exceptions write event payload and traceback to SQL Dead Letter Queue."""
        store = SQLiteEventStore(self.db_file)
        await store.initialize()
        
        # Inject store into high-resiliency Event Bus
        bus = LocalEventBus(dlq_store=store)
        
        async def failing_subscriber(event):
            raise RuntimeError("Simulated Downstream Fatal Crash")
        
        bus.subscribe("system", failing_subscriber)
        
        # Dispatch target event
        event = SystemEvent(action="fault_test")
        event.seal(parent_hashes=[], logical_clock=0)
        
        # Publish - failing subscriber will crash, capturing details to DLQ
        await bus.publish(event)
        
        # Query SQLite directly to assert DLQ insertion
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT event_id, subscriber_name, error_message, stack_trace FROM dead_letter_events LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(row, "Event failure did not generate a Dead Letter Queue record!")
        
        ev_id, sub_name, err_msg, stack = row
        self.assertEqual(ev_id, event.event_id)
        self.assertEqual(err_msg, "Simulated Downstream Fatal Crash")
        self.assertIn("failing_subscriber", sub_name)
        self.assertIn("RuntimeError", stack)

    async def test_07_dlq_jsonl_async_fallback_on_db_crash(self):
        """E2E: Simulates full DB crash/corruption during DLQ write, asserting clean async file logging fallback."""
        from unittest.mock import AsyncMock
        store = SQLiteEventStore(self.db_file)
        await store.initialize()
        
        fallback_file = f"test_fallback_{self.id().split('.')[-1]}.jsonl"
        if os.path.exists(fallback_file): os.remove(fallback_file)
        
        bus = LocalEventBus(dlq_store=store, fallback_log_path=fallback_file)
        
        async def failing_subscriber(event):
            raise RuntimeError("Fatal App Error")
            
        bus.subscribe("system", failing_subscriber)
        
        # Mock DB method to RAISE an OperationalError simulating Disk Full / Corrupt file
        with patch.object(store, "store_dead_letter", new_callable=AsyncMock) as mock_dlq:
            mock_dlq.side_effect = sqlite3.OperationalError("database or disk is full")
            
            event = SystemEvent(action="panic_test")
            event.seal(parent_hashes=[], logical_clock=0)
            
            # Publish: subscriber crashes, then DB crashes, forcing escape hatch!
            await bus.publish(event)
            
            # Yield to ensure async threads completed file I/O
            await asyncio.sleep(0.5)
            
            # Verify the fallback JSONL file now contains the record!
            self.assertTrue(os.path.exists(fallback_file), "Escape Hatch JSONL was not created on DB crash!")
            
            with open(fallback_file, "r") as f:
                lines = f.readlines()
                
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            
            self.assertEqual(record["event_id"], event.event_id)
            self.assertEqual(record["error_message"], "Fatal App Error")
            self.assertIn("database or disk is full", record["dlq_fatal_cause"])
            
        # Cleanup
        if os.path.exists(fallback_file): os.remove(fallback_file)

    async def test_08_redrive_engine_recovery_cycle(self):
        """E2E: Asserts the complete recovery lifecycle using RedriveEngine: Catch -> Fix -> Re-drive -> Clear."""
        store = SQLiteEventStore(self.db_file)
        await store.initialize()
        bus = LocalEventBus(dlq_store=store)
        
        # Stateful subscriber that crashes ONCE and succeeds ONCE
        execution_log = []
        
        async def transient_subscriber(event):
            if len(execution_log) == 0:
                execution_log.append("attempt_1_failed")
                raise RuntimeError("Transient API Crash")
            else:
                execution_log.append("attempt_2_success")
                
        bus.subscribe("system", transient_subscriber)
        
        event = SystemEvent(action="retryable_event")
        event.seal(parent_hashes=[], logical_clock=0)
        
        # First attempt fails -> Writes to DLQ
        await bus.publish(event)
        
        self.assertEqual(len(execution_log), 1)
        letters_pre = await store.get_dead_letters()
        self.assertEqual(len(letters_pre), 1, "Dead letter was not logged in SQLite!")
        
        # Instantiate Redrive Engine and trigger recovery cycle!
        redrive_eng = RedriveEngine(store, bus)
        
        # Assert programmatic list capability
        dead_list = await redrive_eng.list_dead_letters()
        self.assertEqual(len(dead_list), 1)
        
        # Execute bulk redrive
        processed_count = await redrive_eng.redrive_all()
        self.assertEqual(processed_count, 1, "RedriveEngine did not process the dead letter!")
        
        # Yield slightly for thread completions
        await asyncio.sleep(0.1)
        
        # Assertions:
        # 1. The subscriber ran a second time and SUCCEEDED!
        self.assertEqual(len(execution_log), 2)
        self.assertEqual(execution_log[1], "attempt_2_success")
        
        # 2. The DLQ record was purged transactionally!
        letters_post = await store.get_dead_letters()
        self.assertEqual(len(letters_post), 0, "DLQ record was not purged after successful re-processing!")

if __name__ == "__main__":
    unittest.main()
