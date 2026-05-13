from typing import List, Dict, Any
from lifeline.core.events import EventBase, FailureEvent, ToolExecutionEvent, AgentEvent

class ContextRankingEngine:
    """
    Executes situational context relevance boosting.
    Ranks events and state fragments by logical clock recency, workflow status context, 
    and structural causal importance.
    """
    def __init__(self):
        pass

    def rank_and_score(self, raw_materials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Applies Signal Weighting & Situational Relevance Boosting.
        Returns a prioritized list of cognitive fragments with computed scores.
        """
        current_status = raw_materials.get("status", {}).get("current_status", "PENDING")
        
        all_fragments: List[Dict[str, Any]] = []
        
        # 1. Inject Causal Ancestry (high baseline weight)
        for ev in raw_materials.get("causal_ancestry", []):
            score = 0.8  # High baseline for explicit parents
            
            # Failure Boosting: If workflow is in a failure cycle, boost related failures!
            if isinstance(ev, FailureEvent):
                if current_status in ["RETRYING", "FAILED"]:
                    score += 0.5 # Dynamic Escalation Boost
                else:
                    score += 0.2
            
            all_fragments.append({
                "type": "causal_link",
                "event": ev,
                "score": score
            })

        # 2. Inject Temporal Trace (adds chronologic context)
        # We weight by Lamport decay: newer events (higher logical clock) get higher weight
        temp_events = raw_materials.get("chronological_trace", [])
        if temp_events:
            max_clock = max(ev.logical_clock for ev in temp_events) if temp_events else 0
            for ev in temp_events:
                # Avoid duplicating if already in causal list (or just accumulate score)
                # Temporal decay: 0.5 base + recency fraction
                recency = 1.0 if max_clock == 0 else (ev.logical_clock / max_clock)
                score = 0.4 + (recency * 0.3)
                
                all_fragments.append({
                    "type": "temporal_trace",
                    "event": ev,
                    "score": score
                })

        # Deduplicate fragments referencing identical EventIDs, picking the maximum score
        deduped: Dict[str, Dict[str, Any]] = {}
        for f in all_fragments:
            eid = f["event"].event_id
            if eid not in deduped or f["score"] > deduped[eid]["score"]:
                deduped[eid] = f

        # Sort descending by computed relevance score
        ranked_list = list(deduped.values())
        ranked_list.sort(key=lambda x: x["score"], reverse=True)
        
        return ranked_list
