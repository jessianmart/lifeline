import subprocess
import sys
import time

def run_verification_script(script_name: str):
    print(f"\n>>> [RUNNING SMOKE TEST: {script_name}] <<<")
    print("-" * 60)
    t_start = time.perf_counter()
    
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=True,
            text=True,
            timeout=60
        )
        t_end = time.perf_counter()
        
        if result.returncode == 0:
            print(f"[PASS] | Completed in {(t_end - t_start):.2f}s")
            # Print last few lines of output to summarize
            output_lines = result.stdout.strip().split("\n")
            summary = "\n".join(output_lines[-5:])
            print(f"\nSummary Output:\n{summary}\n")
            return True
        else:
            print(f"[FAIL] | Script exited with code {result.returncode}")
            print(f"\nError Output:\n{result.stderr}\n{result.stdout[-500:]}\n")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"[FAIL] | Script {script_name} timed out after 60 seconds.")
        return False
    except Exception as e:
        print(f"[FAIL] | Unexpected error: {str(e)}")
        return False

def main():
    print("==================================================")
    print("   LIFELINE SDK MASTER SMOKE TEST (PROVA DE FOGO)")
    print("==================================================")
    print("Executando a verificação completa de integridade end-to-end...\n")
    
    tests = [
        "verify_stress_run.py",
        "verify_chaos_storm.py",
        "verify_flight_dashboard.py"
    ]
    
    passed_all = True
    for test in tests:
        success = run_verification_script(test)
        if not success:
            passed_all = False
            break
            
    print("=" * 50)
    if passed_all:
        print("      [SUCCESS] MASTER SMOKE TEST COMPLETED [SUCCESS]")
        print("      Todas as fases estao operacionais e integras!")
    else:
        print("      [ERROR] MASTER SMOKE TEST FAILED [ERROR]")
    print("=" * 50)

if __name__ == "__main__":
    main()
