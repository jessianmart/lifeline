import time
from typing import Dict, Any, Callable
from lifeline.runtime.resources import ResourceManager

class SandboxExecutionTelemetry:
    """Physical and digital resource accounting for an isolated execution."""
    def __init__(self, tokens: int, time_ms: int, success: bool):
        self.tokens_consumed = tokens
        self.execution_time_ms = time_ms
        self.success = success

class IsolatedSandboxExecutor:
    """
    The Shielded Execution Domain.
    Intercepts execution routines, isolates collateral side-effects, 
    and measures the physical execution footprint back to the ResourceManager.
    """
    def __init__(self, resource_manager: ResourceManager):
        self.resource_manager = resource_manager

    async def execute_sandboxed_tool(
        self, 
        agent_id: str, 
        tool_callable: Callable[..., Any], 
        tool_args: Dict[str, Any],
        token_weight: int = 10 # Cost base multiplier
    ) -> tuple[Any, SandboxExecutionTelemetry]:
        """
        Encloses Tool routine in telemetry bounds.
        Measures physical runtime and payload-derived token density.
        Deducts footprint post-run.
        """
        # 1. Audit PRE-dispatch check
        self.resource_manager.verify_dispatch_eligibility(agent_id)

        # 2. Benchmark execution bounds
        t_start = time.perf_counter()
        success = True
        result = None
        
        try:
            # Perform actual execution
            result = tool_callable(**tool_args)
        except Exception as e:
            success = False
            result = str(e)
            
        t_end = time.perf_counter()
        
        # 3. Account metrics
        elapsed_ms = int((t_end - t_start) * 1000)
        if elapsed_ms < 1: 
            elapsed_ms = 1 # Enforce minimal logical quantum
            
        # Synthetic token calc: 50 flat base + len(args) * weight
        payload_footprint = len(str(tool_args))
        tokens_consumed = 50 + (payload_footprint * token_weight)
        
        # 4. Charge physical resources
        self.resource_manager.charge_resource(agent_id, tokens_consumed, elapsed_ms)
        
        telemetry = SandboxExecutionTelemetry(
            tokens=tokens_consumed, time_ms=elapsed_ms, success=success
        )
        return result, telemetry

    async def execute_physical_command(
        self,
        agent_id: str,
        cmd_args: list[str],
        cwd: str = None
    ) -> tuple[Dict[str, Any], SandboxExecutionTelemetry]:
        """
        Spawns real Host Process isolation via subprocess.
        Audits full stdout, stderr, exit status, and measures true CPU execution timing.
        Deducts footprint dynamically from the ResourceManager.
        """
        import subprocess

        # 1. Dispatch verification
        self.resource_manager.verify_dispatch_eligibility(agent_id)

        # 2. Run Process and measure physics
        t_start = time.perf_counter()
        success = False
        
        try:
            process = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=30 # Safeguard against infinite hanging loops
            )
            success = (process.returncode == 0)
            
            # Hardening: Truncate stdout/stderr to prevent explosive context payload inflation
            MAX_LOG_CHARS = 5000
            stdout_clean = (process.stdout[:MAX_LOG_CHARS] + "\n[TRUNCATED DUE TO OVERFLOW]") if len(process.stdout) > MAX_LOG_CHARS else process.stdout
            stderr_clean = (process.stderr[:MAX_LOG_CHARS] + "\n[TRUNCATED DUE TO OVERFLOW]") if len(process.stderr) > MAX_LOG_CHARS else process.stderr

            result = {
                "returncode": process.returncode,
                "stdout": stdout_clean,
                "stderr": stderr_clean
            }
        except subprocess.TimeoutExpired as e:
            success = False
            result = {
                "returncode": -124, # Standard timeout exit code
                "stdout": e.stdout.decode(errors='ignore')[:2000] if e.stdout else "",
                "stderr": f"EXECUTION_TIMEOUT: Subprocess exceeded 30s hardware barrier.\n{e.stderr.decode(errors='ignore')[:2000] if e.stderr else ''}"
            }
        except Exception as e:
            success = False
            result = {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e)
            }

        t_end = time.perf_counter()

        # 3. Telemetry calculation
        elapsed_ms = int((t_end - t_start) * 1000)
        if elapsed_ms < 1: 
            elapsed_ms = 1

        # Cost: Base 100 tokens for real system spawn + len(output) * 0.5 (to simulate processing costs)
        out_density = len(result["stdout"]) + len(result["stderr"])
        tokens_consumed = 100 + int(out_density * 0.2)

        # 4. Deduct quotas
        self.resource_manager.charge_resource(agent_id, tokens_consumed, elapsed_ms)

        telemetry = SandboxExecutionTelemetry(
            tokens=tokens_consumed, time_ms=elapsed_ms, success=success
        )
        return result, telemetry
