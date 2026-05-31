import time
from typing import Dict, Optional, Tuple, Any
from .assembly import ContextPayload

class AssembledContextCache:
    """
    High-performance, deterministic cognitive cache.
    Leverages Lamport Logical Clocks & Algorithmic Versions for bulletproof cache keys.
    """
    def __init__(self):
        # Store structure: {cache_key: (timestamp, payload)}
        self._cache: Dict[Tuple[Any, ...], Tuple[float, ContextPayload]] = {}

    def _make_key(self, workflow_id: str, current_logical_clock: int, context_version: str, assembly_version: str) -> Tuple[Any, ...]:
        """Constructs an immutable cache key tuple incorporating algorithmic parameters."""
        return (workflow_id, current_logical_clock, context_version, assembly_version)

    def get(self, workflow_id: str, current_logical_clock: int, context_version: str, assembly_version: str) -> Optional[ContextPayload]:
        """
        Retrieves valid cache entry.
        If ledger has moved or algorithms changed, it results in a cache miss.
        """
        key = self._make_key(workflow_id, current_logical_clock, context_version, assembly_version)
        entry = self._cache.get(key)
        if not entry:
            return None
            
        cache_time, payload = entry
        return payload

    def set(self, workflow_id: str, logical_clock: int, context_version: str, assembly_version: str, payload: ContextPayload) -> None:
        """Caches assembled model coupled to explicit clock & algorithm signatures."""
        key = self._make_key(workflow_id, logical_clock, context_version, assembly_version)
        self._cache[key] = (time.time(), payload)

    def clear(self) -> None:
        self._cache.clear()
