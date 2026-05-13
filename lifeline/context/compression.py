from typing import List, Dict, Any
from pydantic import BaseModel, Field

class ContextBudget(BaseModel):
    """Enforces execution safety limits on context size and analytical depth."""
    max_events: int = 15
    max_failures: int = 3
    max_character_budget: int = 8000

class ContextCompressionEngine:
    """
    Executes Causal Summarization & Collapsing.
    Condenses raw operational materials to preserve crucial decision logic 
    within safe token boundaries.
    """
    def __init__(self, budget: ContextBudget = ContextBudget()):
        self.budget = budget

    def compress(self, ranked_fragments: List[Dict[str, Any]], reconstructed_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Collapses the trace graph by filtering out low-priority events
        until the payload fits tightly within the configured ContextBudget.
        """
        selected = []
        failure_count = 0
        char_count = len(str(reconstructed_state)) # Baseline size of memory state

        for f in ranked_fragments:
            # Limit total count
            if len(selected) >= self.budget.max_events:
                break

            # Limit specific dimension density (Failures)
            from lifeline.core.events import FailureEvent
            if isinstance(f["event"], FailureEvent):
                if failure_count >= self.budget.max_failures:
                    continue
                failure_count += 1

            # Content evaluation
            event_repr = f["event"].model_dump_json()
            if char_count + len(event_repr) > self.budget.max_character_budget:
                # Reached absolute buffer ceiling
                break
            
            char_count += len(event_repr)
            selected.append(f)

        # Sort chronologically (by logical clock) the selected subset to maintain natural narrative
        selected.sort(key=lambda x: x["event"].logical_clock)
        return selected
