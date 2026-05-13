import asyncio
import os
import sys
from devos.swarm import DevOSSwarmOrchestrator

def generate_broken_workspace(branch_count: int):
    """Creates isolated, dedicated Python code files for each concurrent worker branch."""
    print("[PRE-RUN] Seeding isolated workspace directories and module files...")
    for i in range(1, branch_count + 1):
        suffix = chr(64 + i) # A, B, C...
        
        module_path = f"broken_module_{suffix}.py"
        test_path = f"test_broken_{suffix}.py"
        
        # Write broken module
        with open(module_path, "w") as f:
            f.write(f"""def execute_core_computation():
    raise AssertionError("CRITICAL FAILURE IN SEED {suffix}")
""")
            
        # Write corresponding dedicated unit test
        with open(test_path, "w") as f:
            f.write(f"""import unittest
import broken_module_{suffix}

class TestBrokenModule(unittest.TestCase):
    def test_computation(self):
        result = broken_module_{suffix}.execute_core_computation()
        self.assertEqual(result, 42)
""")
            
    print("[PRE-RUN] Seeding finished successfully.\n")

def cleanup_workspace(branch_count: int):
    """Purges the temporary concurrent code files."""
    print("\n[POST-RUN] Cleaning up isolated files...")
    for i in range(1, branch_count + 1):
        suffix = chr(64 + i)
        for f in [f"broken_module_{suffix}.py", f"test_broken_{suffix}.py"]:
            if os.path.exists(f):
                os.remove(f)
    print("[POST-RUN] Workspace purge completed.")

async def main():
    print("==================================================")
    print("   THE CAUSAL STORM: MULTI-AGENT CONCURRENCY RUN")
    print("==================================================\n")

    db_file = "simulation_chaos_storm.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    branch_count = 3
    generate_broken_workspace(branch_count)

    # The corrective patch content (common valid solution)
    fix_patch = """def execute_core_computation():
    return 42
"""

    swarm = DevOSSwarmOrchestrator(db_file, unsafe_allow_host_execution=True)
    await swarm.bootstrap()

    try:
        passed = await swarm.run_chaos_storm(
            workflow_id="wf_storm_99",
            fix_perm_content=fix_patch,
            branch_count=branch_count
        )
        
        print("==================================================")
        if passed:
            print("    CONCURRENCY STORM RESULT: PASS [SUCCESS]")
            print("   Ledger survived concurrent physical load!")
        else:
            print("    CONCURRENCY STORM RESULT: FAIL [ERROR]")
        print("==================================================")
        
    finally:
        cleanup_workspace(branch_count)

if __name__ == "__main__":
    asyncio.run(main())
