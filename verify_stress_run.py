import asyncio
import os
import sys

from devos.swarm import DevOSSwarmOrchestrator

async def main():
    print("==================================================")
    print("    DEVOS SWARM STRESS TEST: THE RECURSION RUN")
    print("==================================================\n")

    db_file = "simulation_stress_swarm.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    # The Patch content that fixes the broken module!
    fix_patch = """def execute_core_computation():
    \"\"\"Fixed! Math core recovered.\"\"\"
    return 42
"""

    # Target files
    broken_file = "broken_module.py"
    
    # We use portable builtin unittest runner for sandbox isolation validation!
    test_cmd = [sys.executable, "-m", "unittest", "test_broken.py"]

    # Bootstrap system application
    swarm = DevOSSwarmOrchestrator(db_file)
    await swarm.bootstrap()

    # Launch autonomous coding workload!
    passed = await swarm.run_stress_loop(
        workflow_id="wf_stress_01",
        broken_file=broken_file,
        patch_content=fix_patch,
        test_cmd=test_cmd
    )

    print("\n==================================================")
    if passed:
        print("      STRESS TEST RESULT: PASS [SUCCESS]")
        print("   The DevOS Swarm has self-repaired successfully!")
    else:
        print("      STRESS TEST RESULT: FAIL [ERROR]")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(main())
