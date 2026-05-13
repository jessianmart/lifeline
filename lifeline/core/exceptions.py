class LifelineError(Exception):
    """Base exception for all Lifeline SDK errors."""
    pass

class EventValidationError(LifelineError):
    """Raised when an event fails schema or integrity validation."""
    pass

class CausalIntegrityError(LifelineError):
    """Raised when the causal lineage of events is broken or invalid."""
    pass

class StateReconstructionError(LifelineError):
    """Raised when state cannot be rebuilt from events."""
    pass

class StorageError(LifelineError):
    """Base exception for storage adapter failures."""
    pass

class EventNotFoundError(StorageError):
    """Raised when an requested event is not found in the store."""
    pass

class ExecutionPolicyError(LifelineError):
    """Raised when execution policy, sandbox bounds, or hardware access is breached."""
    pass
