from typing import List, Dict, Any
from pydantic import BaseModel, Field

class ContextBudget(BaseModel):
    """Enforces execution safety limits on context size and analytical depth."""
    model_config = {"strict": True}
    
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
        Implements dynamic Semantic Collapsing for consecutive Cognitive failures.
        """
        # 0. BUDGET SHIELD: Collapse consecutive cognitive failures loops
        compacted_fragments = self._collapse_cognitive_failures(ranked_fragments)
        
        selected = []
        failure_count = 0
        char_count = len(str(reconstructed_state)) # Baseline size of memory state

        for f in compacted_fragments:
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

    def _collapse_cognitive_failures(self, fragments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Scans sequential execution trace to detect and compress consecutive cognitive failure loops
        into concise synthetic summary tokens, shielding LLM context sizes.
        """
        from lifeline.core.events import FailureEvent
        
        if not fragments:
            return []
            
        # Sort chronologically to audit authentic execution sequence
        chrono = sorted(fragments, key=lambda x: x["event"].logical_clock)
        
        result = []
        i = 0
        n = len(chrono)
        
        while i < n:
            current_f = chrono[i]
            current_ev = current_f["event"]
            
            if isinstance(current_ev, FailureEvent) and current_ev.failure_domain == "COGNITIVE":
                # Scan look-ahead for immediate consecutive cognitive failures
                consecutive = [current_f]
                j = i + 1
                while j < n:
                    next_f = chrono[j]
                    next_ev = next_f["event"]
                    if isinstance(next_ev, FailureEvent) and next_ev.failure_domain == "COGNITIVE":
                        consecutive.append(next_f)
                        j += 1
                    else:
                        break
                
                if len(consecutive) > 1:
                    # Multi-attempt failure loop detected: Compress!
                    latest_f = consecutive[-1]
                    latest_ev = latest_f["event"]
                    
                    # Synthesize consolidated representation inheriting latest attributes
                    summary_ev = latest_ev.model_copy(deep=True)
                    summary_ev.error_message = (
                        f"[BUDGET SHIELD COLLAPSE] Agent entered a {len(consecutive)}-attempt failure loop. "
                        f"Latest parsing error: {latest_ev.error_message}"
                    )
                    summary_ev.stack_trace = "Stacked recursion traces collapsed to conserve context bytes."
                    summary_ev.contextual_remedy = "Verify structural json compliance and strictly avoid hallucinations."
                    
                    # Insert the collapsed synthetic variant with the original fragment score
                    collapsed_f = {**latest_f, "event": summary_ev}
                    result.append(collapsed_f)
                    i = j
                else:
                    result.append(current_f)
                    i += 1
            else:
                result.append(current_f)
                i += 1
                
        # Re-sort back by rank score to maintain the importance metrics during truncation loop
        return sorted(result, key=lambda x: x.get("score", 0.0), reverse=True)
