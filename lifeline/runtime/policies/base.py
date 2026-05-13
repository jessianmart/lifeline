from typing import List, Set, Dict, Optional
from lifeline.core.exceptions import EventValidationError

class ExecutionPolicyError(Exception):
    """Raised when a runtime policy guard blocks an operation."""
    pass

class PolicyEngine:
    """
    Enforces compliance, safety limits, and access capability rules 
    across execution nodes, agents, and external tools.
    Acts as a runtime compliance wall preventing uncertified executions.
    """
    def __init__(self):
        # Simple internal registry of agent capabilities for the MVP
        self._agent_capabilities: Dict[str, Set[str]] = {}

    def register_agent_capabilities(self, agent_id: str, capabilities: List[str]) -> None:
        """Grants a list of capabilities to an agent runtime scope."""
        self._agent_capabilities[agent_id] = set(capabilities)

    def verify_tool_execution(self, agent_id: str, tool_name: str, required_capabilities: List[str]) -> bool:
        """
        Evaluates whether an agent runtime possesses all required authorization flags 
        to trigger an external capability.
        """
        # If no capabilities required, allow by default for minimal friction
        if not required_capabilities:
            return True
            
        agent_caps = self._agent_capabilities.get(agent_id, set())
        
        # Check if required subset is missing
        missing = set(required_capabilities) - agent_caps
        if missing:
            raise ExecutionPolicyError(
                f"Security Guard: Agent '{agent_id}' rejected executing tool '{tool_name}'. "
                f"Missing critical capabilities: {list(missing)}"
            )
            
        return True

    def verify_branch_permission(self, agent_id: str, workflow_id: str) -> bool:
        """
        Validates if an agent possesses write permission to create 
        bifurcated operational branches on a workflow ledger.
        """
        agent_caps = self._agent_capabilities.get(agent_id, set())
        if "lineage_write" not in agent_caps and "admin" not in agent_caps:
             raise ExecutionPolicyError(
                f"Ledger Policy: Agent '{agent_id}' possesses read-only lineage access. "
                "Cannot perform operational branch forks."
             )
        return True
