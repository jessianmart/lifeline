import math
from typing import List, Optional, Dict, Any
from lifeline.context.memory import BaseVectorMemory, VectorRecord

class LocalVectorMemory(BaseVectorMemory):
    """
    Concrete, high-performance in-memory vector storage.
    Enforces strict dimension alignment and calculates cosine similarity using pure Python.
    """
    def __init__(self, embedding_dimension: int = 768, persistence_path: Optional[str] = None):
        self.embedding_dimension = embedding_dimension
        self.persistence_path = persistence_path
        self._records: List[VectorRecord] = []
        
        if self.persistence_path:
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        import os
        import json
        if os.path.exists(self.persistence_path):
            try:
                with open(self.persistence_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._records = [VectorRecord.model_validate(item) for item in data]
            except Exception as e:
                import sys
                print(f"[VectorMemory] Failed to load persistent records from {self.persistence_path}: {e}", file=sys.stderr)

    def _save_to_disk(self) -> None:
        import os
        import json
        if self.persistence_path:
            try:
                dir_name = os.path.dirname(self.persistence_path)
                if dir_name:
                    os.makedirs(dir_name, exist_ok=True)
                with open(self.persistence_path, "w", encoding="utf-8") as f:
                    json.dump([item.model_dump() for item in self._records], f, ensure_ascii=False, indent=2)
            except Exception as e:
                import sys
                print(f"[VectorMemory] Failed to save persistent records to {self.persistence_path}: {e}", file=sys.stderr)

    def _dot_product(self, v1: List[float], v2: List[float]) -> float:
        return sum(x * y for x, y in zip(v1, v2))

    def _magnitude(self, v: List[float]) -> float:
        return math.sqrt(sum(x * x for x in v))

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        mag1 = self._magnitude(v1)
        mag2 = self._magnitude(v2)
        if mag1 == 0.0 or mag2 == 0.0:
            return 0.0
        return self._dot_product(v1, v2) / (mag1 * mag2)

    async def insert_episodic_node(self, record: VectorRecord) -> bool:
        """
        Inserts a new VectorRecord after verifying embedding dimension bounds.
        """
        if len(record.vector) != self.embedding_dimension:
            raise ValueError(
                f"Dimension Mismatch: Attempted to insert a vector of size {len(record.vector)} "
                f"but this LocalVectorMemory instance expects exactly {self.embedding_dimension} dimensions."
            )
        self._records.append(record)
        self._save_to_disk()
        return True

    async def search_related_episodes(
        self, 
        query_vector: List[float], 
        limit: int = 5,
        filter_workflow_id: Optional[str] = None
    ) -> List[VectorRecord]:
        """
        Finds the closest semantic episodes using cosine similarity.
        """
        if len(query_vector) != self.embedding_dimension:
            raise ValueError(
                f"Dimension Mismatch: Query vector size {len(query_vector)} "
                f"does not match expected size of {self.embedding_dimension} dimensions."
            )

        scored_records = []
        for record in self._records:
            # If workflow filter is applied, inspect metadata
            if filter_workflow_id:
                record_wf = record.metadata.get("workflow_id")
                if record_wf != filter_workflow_id:
                    continue

            similarity = self._cosine_similarity(query_vector, record.vector)
            scored_records.append((similarity, record))

        # Sort descending by similarity score
        scored_records.sort(key=lambda x: x[0], reverse=True)
        return [record for _, record in scored_records[:limit]]
