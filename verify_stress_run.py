import asyncio
import os
import sys
from devos.swarm import DevOSSwarmOrchestrator

def generate_broken_workspace():
    # Creates isolated workspace for Single Branch (A)
    with open("broken_module_A.py", "w") as f:
        f.write("def execute_core_computation(): raise AssertionError('Initial Seed Break')\n")
    with open("test_broken_A.py", "w") as f:
        f.write("""import unittest
import broken_module_A
class TestBroken(unittest.TestCase):
    def test_main(self): self.assertEqual(broken_module_A.execute_core_computation(), 42)
""")

def cleanup_workspace():
    for f in ["broken_module_A.py", "test_broken_A.py"]:
        if os.path.exists(f): os.remove(f)

async def main():
    print("==================================================")
    print("    DEVOS SWARM STRESS TEST: THE RECURSION RUN")
    print("==================================================\n")

    db_file = "simulation_stress_swarm.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    generate_broken_workspace()

    # The Patch content that fixes the broken module!
    fix_patch = """def execute_core_computation():
    return 42
"""

    swarm = DevOSSwarmOrchestrator(db_file, unsafe_allow_host_execution=True)
    await swarm.bootstrap()

    try:
        # Launch autonomous coding workload with single branch
        passed = await swarm.run_chaos_storm(
            workflow_id="wf_stress_01",
            fix_perm_content=fix_patch,
            branch_count=1
        )

        print("\n==================================================")
        if passed:
            print("      STRESS TEST RESULT: PASS [SUCCESS]")
            print("   The DevOS Swarm has self-repaired successfully!")
        else:
            print("      STRESS TEST RESULT: FAIL [ERROR]")
        print("==================================================")

    finally:
        cleanup_workspace()

if __name__ == "__main__":
    asyncio.run(main())
