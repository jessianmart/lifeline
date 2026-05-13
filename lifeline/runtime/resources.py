from typing import Dict
from pydantic import BaseModel, Field

class ResourceExhaustionError(Exception):
    """Raised when a transactional thread breaches authorized resource boundaries."""
    pass

class ResourceQuota(BaseModel):
    """System-level allocations for CPU (ms) and computational currency (Tokens)."""
    max_tokens: int = 10000
    consumed_tokens: int = 0
    
    max_execution_ms: int = 30000
    consumed_execution_ms: int = 0

    def check_availability(self, est_tokens: int = 0) -> bool:
        """Dry-run check. Returns false if estimated execution breaches ceiling."""
        return (self.consumed_tokens + est_tokens) <= self.max_tokens

class ResourceManager:
    """
    Governance entity for computational physics.
    Enforces strict execution boundaries and records hardware footprint telemetries.
    """
    def __init__(self):
        # Dictionary indexing quotas: {agent_id: ResourceQuota}
        self._quotas: Dict[str, ResourceQuota] = {}

    def provision_quota(self, agent_id: str, quota: ResourceQuota) -> None:
        """Allocates limits to a designated process."""
        self._quotas[agent_id] = quota

    def get_quota(self, agent_id: str) -> ResourceQuota:
        """Retrieves allocation record, supplying defaults if unprovisioned."""
        return self._quotas.setdefault(agent_id, ResourceQuota())

    def charge_resource(self, agent_id: str, tokens: int, duration_ms: int) -> None:
        """Deducts physical resources post-operation."""
        quota = self.get_quota(agent_id)
        quota.consumed_tokens += tokens
        quota.consumed_execution_ms += duration_ms

    def verify_dispatch_eligibility(self, agent_id: str) -> None:
        """
        Kernel security verification before release.
        Locks executions exceeding critical thresholds.
        """
        quota = self.get_quota(agent_id)
        if quota.consumed_tokens >= quota.max_tokens:
            raise ResourceExhaustionError(
                f"Resource Exhausted: Agent '{agent_id}' hit token ceiling ({quota.consumed_tokens}/{quota.max_tokens})."
            )
        if quota.consumed_execution_ms >= quota.max_execution_ms:
            raise ResourceExhaustionError(
                f"Resource Exhausted: Agent '{agent_id}' hit execution time limit ({quota.consumed_execution_ms}/{quota.max_execution_ms}ms)."
            )
