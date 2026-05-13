import time
from typing import Dict, List, Any

class SystemicProfiler:
    """
    The Central Diagnostic Hub of the Cognitive OS.
    Measures and aggregates sub-system physical durations, queues, and cache states.
    """
    def __init__(self):
        # Context Engine Telemetry
        self.reconstruction_times: List[float] = []
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        
        # Scheduler Telemetry
        self.scheduler_ticks: int = 0
        self.queue_depths_pending: List[int] = []
        self.queue_depths_blocked: List[int] = []
        self.active_processes: int = 0

    def record_context_assembly(self, duration_ms: float, is_hit: bool):
        """Logs context snapshot assembly duration and logical cache validity."""
        self.reconstruction_times.append(duration_ms)
        if is_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    def record_scheduler_tick(self, pending: int, blocked: int, active_count: int):
        """Captures real-time scheduler task queue density and active OS threads."""
        self.scheduler_ticks += 1
        self.queue_depths_pending.append(pending)
        self.queue_depths_blocked.append(blocked)
        self.active_processes = active_count

    def get_snapshot(self) -> Dict[str, Any]:
        """Generates atomic dashboard payload of the current system health."""
        avg_reconstruction = (sum(self.reconstruction_times) / len(self.reconstruction_times)) if self.reconstruction_times else 0.0
        
        total_cache_lookups = self.cache_hits + self.cache_misses
        hit_ratio = (self.cache_hits / total_cache_lookups * 100.0) if total_cache_lookups > 0 else 0.0
        
        avg_pending = (sum(self.queue_depths_pending) / len(self.queue_depths_pending)) if self.queue_depths_pending else 0.0
        avg_blocked = (sum(self.queue_depths_blocked) / len(self.queue_depths_blocked)) if self.queue_depths_blocked else 0.0
        
        return {
            "scheduler_ticks": self.scheduler_ticks,
            "avg_pending_queue": round(avg_pending, 2),
            "avg_blocked_queue": round(avg_blocked, 2),
            "active_processes": self.active_processes,
            "avg_reconstruction_ms": round(avg_reconstruction, 3),
            "cache_hit_ratio": round(hit_ratio, 1),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses
        }

# Global kernel observer to prevent complex DI overhead during stress loops
kernel_profiler = SystemicProfiler()
