from typing import List, Dict, Any, Literal
from lifeline.core.events import BranchMergeEvent
from lifeline.graph.lineage import OperationalLineageGraph
from lifeline.engines.event_engine import EventEngine
from lifeline.engines.state_engine import StateEngine

class BranchReconciler:
    """
    Resolves operational divergences in the causal graph.
    Fuses two separate branch realities back into a single unified State model.
    """
    def __init__(self, event_engine: EventEngine, state_engine: StateEngine):
        self.engine = event_engine
        self.state_engine = state_engine
        self.graph = OperationalLineageGraph(event_engine.store)

    async def reconcile_branches(
        self, 
        workflow_id: str, 
        event_id_a: str, 
        event_id_b: str,
        strategy: Literal["override_with_b", "keep_both_merged"] = "keep_both_merged"
    ) -> str:
        """
        Finds mutual convergent origin, extracts differences, and emits 
        a BranchMergeEvent to merge the DAG paths.
        Returns the resulting EventID of the merge node.
        """
        # 1. Graph Traversal to find convergence root
        convergent_root = await self.graph.find_convergent_ancestor(event_id_a, event_id_b)
        
        # 2. Extract state snapshots up to event_id_a and event_id_b
        # For simplicity in MVP, we rebuild states by traversing streams manually or injecting anchor
        # In full runtime, StateEngine.rebuild_workflow_state can take a 'target_event_id' to compute partial states!
        # Since rebuild_workflow_state processes all, we simulate the merge here by fetching both partial streams.
        
        # Construct state at leaf A
        ancestry_a = await self.graph.get_causal_ancestry(event_id_a)
        state_a = await self.state_engine.rebuild_from_snapshot({}, ancestry_a)
        
        # Construct state at leaf B
        ancestry_b = await self.graph.get_causal_ancestry(event_id_b)
        state_b = await self.state_engine.rebuild_from_snapshot({}, ancestry_b)
        
        # 3. Reconcile State Dict based on Strategy
        merged_state = {}
        if strategy == "override_with_b":
            merged_state = {**state_a, **state_b}
        else:
            # Complex Merger: Keep all distinct keys, listify collisions
            all_keys = set(state_a.keys()) | set(state_b.keys())
            for k in all_keys:
                val_a = state_a.get(k)
                val_b = state_b.get(k)
                if val_a is not None and val_b is not None and val_a != val_b:
                    merged_state[k] = [val_a, val_b]  # Represent collision clearly
                else:
                    merged_state[k] = val_a if val_a is not None else val_b

        # 4. Commit Convergence Event joining both parents!
        merge_event = BranchMergeEvent(
            workflow_id=workflow_id,
            converged_from_branches=[event_id_a, event_id_b],
            reconciliation_strategy=strategy,
            merged_state_summary=merged_state,
            parent_event_ids=[event_id_a, event_id_b] # Join link in the DAG!
        )
        
        # Emit seals the hash securely linking BOTH parents
        merge_event_id = await self.engine.emit(merge_event)
        return merge_event_id
