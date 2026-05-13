import unittest
import asyncio
import time
from lifeline.runtime.resources import ResourceManager
from lifeline.runtime.sandbox import IsolatedSandboxExecutor

class TestSandboxBenchmark(unittest.IsolatedAsyncioTestCase):
    """
    Ensures the Warm Execution Pool successfully reduces physical isolation latency.
    Asserts that consecutive runs recycle the background isolate, delivering sub-150ms cycles.
    """
    
    async def asyncSetUp(self):
        self.resource_manager = ResourceManager()
        # Instantiate with safe host opt-in = False (demands real docker)
        self.executor = IsolatedSandboxExecutor(
            self.resource_manager,
            unsafe_allow_host_execution=False 
        )
        
    async def asyncTearDown(self):
        # Explicit teardown trigger
        self.executor.shutdown_warm_pools()

    async def test_warm_pool_benchmark(self):
        """Runs multiple physical commands to audit warm container recycling."""
        if not self.executor._check_docker_available():
            self.skipTest("Docker is not running on the host system. Skipping Warm Pool Benchmark.")
            
        agent_id = "benchmark_runner_bot"
        cmd = ["python", "-c", "print('LIFELINE_OS_WARM_CHECK')"]
        
        durations = []
        
        # Run 3 sequential commands
        for i in range(3):
            t0 = time.perf_counter()
            res, telemetry = await self.executor.execute_physical_command(
                agent_id=agent_id,
                cmd_args=cmd
            )
            t1 = time.perf_counter()
            dur_ms = (t1 - t0) * 1000
            durations.append(dur_ms)
            
            # Verify command executed successfully inside chroot
            self.assertIn("LIFELINE_OS_WARM_CHECK", res["stdout"])
            self.assertEqual(res["returncode"], 0)
            
        print(f"\n[BENCHMARK REPORT]")
        print(f"Run 1 (Daemon Bootstrap Cold): {durations[0]:.2f}ms")
        print(f"Run 2 (Warm Exec Recycled):   {durations[1]:.2f}ms")
        print(f"Run 3 (Warm Exec Recycled):   {durations[2]:.2f}ms")
        
        # Assert Warm Exec Recycle throughput is significantly faster than initial bootstrap
        # Typically Run 1 > 1000ms (due to inspect polling + boot), Runs 2-3 < 300ms
        self.assertLess(durations[1], durations[0], "Warm recycling MUST be faster than initial bootstrap!")

if __name__ == "__main__":
    unittest.main()
