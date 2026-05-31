from typing import Dict, List, Any, Optional
from lifeline.context.memory import BaseVectorMemory, VectorRecord
from lifeline.context.local import LocalVectorMemory

class SemanticMemory:
    """Tier 4: Long-term associations and conceptual similarity embeddings."""
    def __init__(self, vector_memory: Optional[BaseVectorMemory] = None):
        self.vector_memory = vector_memory or LocalVectorMemory(embedding_dimension=768)
        self._legacy_associations: Dict[str, List[str]] = {}

    def associate(self, concept: str, node_id: str) -> None:
        """
        Legacy keyword-based association.
        """
        self._legacy_associations.setdefault(concept.lower(), []).append(node_id)

    def find_similar_nodes(self, concept: str) -> List[str]:
        """
        Legacy keyword-based lookup.
        """
        return self._legacy_associations.get(concept.lower(), [])

    async def insert_vector_record(self, record: VectorRecord) -> bool:
        """
        Inserts a real VectorRecord into the underlying vector storage.
        """
        return await self.vector_memory.insert_episodic_node(record)

    async def search_vectors(
        self, 
        query_vector: List[float], 
        limit: int = 5, 
        filter_workflow_id: Optional[str] = None
    ) -> List[VectorRecord]:
        """
        Searches the semantic space for matching VectorRecords.
        """
        return await self.vector_memory.search_related_episodes(
            query_vector, 
            limit=limit, 
            filter_workflow_id=filter_workflow_id
        )
