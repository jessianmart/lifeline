import time
import os
import sys
import subprocess
from typing import Dict, Any, Callable
from lifeline.runtime.resources import ResourceManager
from lifeline.core.exceptions import ExecutionPolicyError

class SandboxExecutionTelemetry:
    """Physical and digital resource accounting for an isolated execution."""
    def __init__(self, tokens: int, time_ms: int, success: bool):
        self.tokens_consumed = tokens
        self.execution_time_ms = time_ms
        self.success = success

class IsolatedSandboxExecutor:
    """
    The Shielded Execution Domain.
    Enforces physical process sandboxing via strict container namespaces (Docker)
    imposing rigid cgroup caps (--memory, --cpus) and zero-trust network blocking.
    Enforces hard-failure defaults on host CPU access to protect infrastructure.
    """
    def __init__(self, resource_manager: ResourceManager, unsafe_allow_host_execution: bool = False):
        self.resource_manager = resource_manager
        self.unsafe_allow_host_execution = unsafe_allow_host_execution
        self._docker_cached_status = None

    def _check_docker_available(self) -> bool:
        """Probes local daemon for containerization capabilities."""
        if self._docker_cached_status is not None:
            return self._docker_cached_status
        try:
            # Check if docker CLI exists and daemon responds
            res = subprocess.run(["docker", "info"], capture_output=True, timeout=3)
            self._docker_cached_status = (res.returncode == 0)
        except Exception:
            self._docker_cached_status = False
        return self._docker_cached_status

    async def execute_sandboxed_tool(
        self, 
        agent_id: str, 
        tool_callable: Callable[..., Any], 
        tool_args: Dict[str, Any],
        token_weight: int = 10
    ) -> tuple[Any, SandboxExecutionTelemetry]:
        """Encloses In-Memory Tool routine in telemetry bounds."""
        self.resource_manager.verify_dispatch_eligibility(agent_id)
        t_start = time.perf_counter()
        success = True
        result = None
        
        try:
            result = tool_callable(**tool_args)
        except Exception as e:
            success = False
            result = str(e)
            
        t_end = time.perf_counter()
        elapsed_ms = max(int((t_end - t_start) * 1000), 1)
        
        payload_footprint = len(str(tool_args))
        tokens_consumed = 50 + (payload_footprint * token_weight)
        self.resource_manager.charge_resource(agent_id, tokens_consumed, elapsed_ms)
        
        return result, SandboxExecutionTelemetry(tokens=tokens_consumed, time_ms=elapsed_ms, success=success)

    async def execute_physical_command(
        self,
        agent_id: str,
        cmd_args: list[str],
        cwd: str = None
    ) -> tuple[Dict[str, Any], SandboxExecutionTelemetry]:
        """
        Spawns high-security physical execution isolation.
        Prioritizes a disposable container isolate with:
        - `--network none` (radical data exfiltration barrier)
        - `--memory="512m"` (cgroups RAM envelope)
        - `--cpus="0.5"` (hyperthread throttle)
        
        If Docker is down, strictly blocks execution (ExecutionPolicyError) 
        unless unsafe opt-in is explicitly enabled.
        """
        # 1. Pre-check quota bounds
        self.resource_manager.verify_dispatch_eligibility(agent_id)
        t_start = time.perf_counter()
        
        execution_dir = cwd or os.getcwd()
        docker_mode = self._check_docker_available()
        
        final_cmd = []
        
        # 2. ENFORCE ISOLATION POLICY
        if docker_mode:
            # Normalize host command executables to fit the target Linux python container
            containerized_args = list(cmd_args)
            if containerized_args and ("python" in containerized_args[0].lower() or containerized_args[0] == sys.executable):
                containerized_args[0] = "python"
                
            # Standardize directory slashes for Windows Host -> Docker mounting compatibility
            clean_cwd = os.path.abspath(execution_dir).replace("\\", "/")
            
            # Build hard-walled secure wrapper
            final_cmd = [
                "docker", "run", "--rm",
                "--network", "none",
                "--memory", "512m",
                "--cpus", "0.5",
                "-v", f"{clean_cwd}:/usr/src/app",
                "-w", "/usr/src/app",
                "python:3.11-slim"
            ] + containerized_args
            
        else:
            # Docker unavailable: Evaluate unsafe fallback opt-in
            if not self.unsafe_allow_host_execution:
                raise ExecutionPolicyError(
                    "CRITICAL SECURITY DENIAL: Real Container Sandbox (Docker) is not available. "
                    "Aborting arbitrary agent code execution to protect Host OS integrity. "
                    "To bypass for testing, instantiate with unsafe_allow_host_execution=True."
                )
            
            print(f"[SECURITY WARNING] Host Execution Fallback active for Agent {agent_id}! Executing arbitrary code directly on CPU.", file=sys.stderr)
            final_cmd = cmd_args

        # 3. Execute process under strict 30s timeout limits
        success = False
        try:
            # Execute resolved command sequence
            process = subprocess.run(
                final_cmd,
                capture_output=True,
                text=True,
                cwd=execution_dir if not docker_mode else None, # CWD is inside container's -w
                timeout=30
            )
            success = (process.returncode == 0)
            
            # Prevent explosive memory context bloat by truncating large logs
            MAX_LOG = 5000
            stdout_clean = (process.stdout[:MAX_LOG] + "\n[LOG TRUNCATED]") if len(process.stdout) > MAX_LOG else process.stdout
            stderr_clean = (process.stderr[:MAX_LOG] + "\n[LOG TRUNCATED]") if len(process.stderr) > MAX_LOG else process.stderr

            result = {
                "returncode": process.returncode,
                "stdout": stdout_clean,
                "stderr": stderr_clean,
                "isolated_via": "DockerContainer" if docker_mode else "HostSubprocess"
            }
            
        except subprocess.TimeoutExpired as e:
            success = False
            result = {
                "returncode": -124,
                "stdout": e.stdout.decode(errors='ignore')[:2000] if e.stdout else "",
                "stderr": "EXECUTION_TIMEOUT: Hardware quota breached after 30 seconds.",
                "isolated_via": "DockerContainer" if docker_mode else "HostSubprocess"
            }
        except Exception as e:
            success = False
            result = {
                "returncode": -1,
                "stdout": "",
                "stderr": f"EXECUTION_ERROR: Underlying process launch failed: {str(e)}",
                "isolated_via": "DockerContainer" if docker_mode else "HostSubprocess"
            }

        # 4. Compute final physics telemetry
        t_end = time.perf_counter()
        elapsed_ms = max(int((t_end - t_start) * 1000), 1)

        # Token Density charging logic based on output size
        out_size = len(result["stdout"]) + len(result["stderr"])
        tokens_consumed = 150 + int(out_size * 0.2) # Flat charge for high-barrier spawning

        self.resource_manager.charge_resource(agent_id, tokens_consumed, elapsed_ms)
        
        return result, SandboxExecutionTelemetry(tokens=tokens_consumed, time_ms=elapsed_ms, success=success)
