import unittest
import asyncio
import os
import sys
import sqlite3
import json

from devos.swarm import DevOSSwarmOrchestrator
from lifeline.engines.replay_engine import ReplayEngine
from lifeline.adapters.observability.profiler import kernel_profiler
from lifeline.runtime.resources import ResourceQuota

class TestLifelineE2E(unittest.IsolatedAsyncioTestCase):
    """
    Production E2E Test Suite for Lifeline Cognitive Hypervisor.
    Validates End-to-End Causal Storms, Drift Analysis, and Physical Sandboxing under standard CI tools.
    """
    
    def setUp(self):
        self.db_file = f"test_e2e_run_{self.id().split('.')[-1]}.db"
        self.branch_files = []

    def tearDown(self):
        # Purge dynamic database
        if os.path.exists(self.db_file):
            os.remove(self.db_file)
        
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
        """E2E Validation: Single-agent autonomous lifecycle (Bootstrap -> Patch -> Sandboxed Test -> Success)"""
        self._generate_workspace(["A"])
        
        swarm = DevOSSwarmOrchestrator(self.db_file)
        await swarm.bootstrap()
        
        fix_patch = "def execute_core_computation(): return 42\n"
        
        passed = await swarm.run_chaos_storm(
            workflow_id="wf_e2e_01",
            fix_perm_content=fix_patch,
            branch_count=1
        )
        
        self.assertTrue(passed, "E2E Swarm failed to autonomously repair the single-branch module.")

    async def test_02_concurrency_storm_integrity(self):
        """E2E Validation: Parallel fork bomb (3 concurrent workers, asyncio.gather, non-blocking dispatches)"""
        self._generate_workspace(["A", "B", "C"])
        
        swarm = DevOSSwarmOrchestrator(self.db_file)
        await swarm.bootstrap()
        
        fix_patch = "def execute_core_computation(): return 42\n"
        
        passed = await swarm.run_chaos_storm(
            workflow_id="wf_e2e_02",
            fix_perm_content=fix_patch,
            branch_count=3
        )
        
        self.assertTrue(passed, "E2E Concurrency Storm failed with 3 concurrent branches.")

    async def test_03_drift_fault_detection(self):
        """E2E Validation: Drift validation scanner asserts true on physical database corruption injection."""
        self._generate_workspace(["A"])
        
        swarm = DevOSSwarmOrchestrator(self.db_file)
        await swarm.bootstrap()
        
        fix_patch = "def execute_core_computation(): return 42\n"
        
        # Step 1: Create clean workflow
        await swarm.run_chaos_storm(
            workflow_id="wf_e2e_03",
            fix_perm_content=fix_patch,
            branch_count=1
        )
        
        # Step 2: Inject drift attack directly in SQLite!
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT event_id, logical_clock, payload FROM events ORDER BY logical_clock DESC LIMIT 1")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        
        target_id, _, raw_payload = row
        payload_dict = json.loads(raw_payload)
        # Break Lamport invariant by forcing Child Clock to 1
        payload_dict["logical_clock"] = 1
        
        cursor.execute(
            "UPDATE events SET logical_clock = 1, payload = ? WHERE event_id = ?",
            (json.dumps(payload_dict), target_id)
        )
        conn.commit()
        conn.close()
        
        # Step 3: Assert that Drift Detector catches the violation
        fresh_swarm = DevOSSwarmOrchestrator(self.db_file)
        await fresh_swarm.bootstrap()
        replay_engine = ReplayEngine(fresh_swarm.event_engine)
        
        drifted, diag_msg = await replay_engine.verify_execution_drift("wf_e2e_03")
        
        self.assertTrue(drifted, "Drift Detector failed to flag a physical clock violation!")
        self.assertIn("CLOCK DRIFT DETECTED", diag_msg)

    async def test_04_telemetry_profiling_data(self):
        """E2E Validation: The SystemicProfiler collects accurate non-zero measurements during workflows."""
        # Run a small flow to generate telemetry
        self._generate_workspace(["A"])
        swarm = DevOSSwarmOrchestrator(self.db_file)
        await swarm.bootstrap()
        
        await swarm.run_chaos_storm(
            workflow_id="wf_e2e_04",
            fix_perm_content="def execute_core_computation(): return 42\n",
            branch_count=1
        )
        
        metrics = kernel_profiler.get_snapshot()
        
        self.assertGreater(metrics["scheduler_ticks"], 0, "Profiler did not record any scheduler ticks.")
        self.assertGreater(metrics["avg_reconstruction_ms"], 0.0, "Profiler reported 0ms context reconstruction time.")
        self.assertGreaterEqual(metrics["cache_hit_ratio"], 0.0, "Profiler cache hit ratio is invalid.")

if __name__ == "__main__":
    unittest.main()
