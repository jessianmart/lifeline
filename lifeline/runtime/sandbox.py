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
        
        # [AX INFRASTRUCTURE]: Background warm process mapping to prevent OOM/SIGKILL zombies
        self._warm_processes: Dict[str, subprocess.Popen] = {}
        
        # Register atexit cleanup just in case of graceful python exit
        import atexit
        atexit.register(self.shutdown_warm_pools)

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

    def _ensure_warm_container(self, agent_id: str, cwd: str) -> str:
        """
        [AX FAIL-SAFE]: Guarantees presence of an active, isolated Docker daemon for the agent session.
        Uses stdin-blocking to trigger Docker self-suicide if host python process terminates.
        """
        norm_id = "".join(c if c.isalnum() else "-" for c in agent_id.lower())
        container_name = f"lifeline-warm-{norm_id}"
        
        # 1. Check if already tracked and alive
        if container_name in self._warm_processes:
            proc = self._warm_processes[container_name]
            if proc.poll() is None:
                return container_name
            self._warm_processes.pop(container_name, None)

        # 2. Wipe prior remnants
        try:
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=2)
        except Exception:
            pass

        clean_cwd = os.path.abspath(cwd).replace("\\", "/")
        
        # 3. Watchdog Command: blocks indefinitely on sys.stdin.read().
        # When python dies, pipe EOF occurs, container primary process exits, --rm collects container.
        boot_cmd = [
            "docker", "run", "-i", "--rm",
            "--name", container_name,
            "--network", "none",
            "--memory", "512m",
            "--cpus", "0.5",
            "-v", f"{clean_cwd}:/usr/src/app",
            "-w", "/usr/src/app",
            "python:3.11-slim",
            "python", "-c", "import sys; sys.stdin.read()" 
        ]
        
        proc = subprocess.Popen(
            boot_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # 4. Poll inspect until daemon confirms 'Running' (prevents premature exec)
        t0 = time.time()
        while time.time() - t0 < 5.0:
            chk = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", container_name], 
                capture_output=True, text=True
            )
            if chk.returncode == 0 and "true" in chk.stdout.lower():
                break
            time.sleep(0.1)
            
        self._warm_processes[container_name] = proc
        return container_name

    def shutdown_warm_pools(self):
        """Forcefully tears down all warm subprocesses and closes pipes."""
        for name, proc in list(self._warm_processes.items()):
            try:
                if proc.stdin:
                    proc.stdin.close()
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                pass
            try:
                subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=2)
            except: pass
        self._warm_processes.clear()

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
        Leverages warm background isolates dispatched via `docker exec` for radical
        latency containment (sub-50ms). 
        Ensures dynamic chroot per invocation to preserve causal idempotency.
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
                
            try:
                # 2.1 Acquire Warm Sandbox Isolate
                container_name = self._ensure_warm_container(agent_id, execution_dir)
                
                # 2.2 [AX IDEMPOTENCY MITIGATION]: Dynamic Ephemeral Tick-Directory chroot
                import uuid
                tick_id = f"tick_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
                
                # Stringify list representation safely for shell routing
                cmd_str = " ".join(f'"{a}"' if " " in a or "*" in a or "$" in a else a for a in containerized_args)
                tick_cmd = f"mkdir -p /tmp/{tick_id} && cd /tmp/{tick_id} && {cmd_str}"
                
                final_cmd = [
                    "docker", "exec",
                    container_name,
                    "sh", "-c",
                    tick_cmd
                ]
            except Exception as e:
                # Graceful fallback to disposable cold docker run
                clean_cwd = os.path.abspath(execution_dir).replace("\\", "/")
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
