from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class VectorRecord(BaseModel):
    """Rigid metadata alignment for semantic embeddings."""
    model_config = {"strict": True}
    
    vector: List[float]
    payload_text: str
    
    # [AX SEMANTIC INTEGRITY]: Every semantic insertion MUST link to its 
    # Lamport Causal origin. Disconnection causes hallucinated associative retrieval.
    causal_event_id: str
    
    metadata: Dict[str, Any] = Field(default_factory=dict)

class BaseVectorMemory(ABC):
    """
    Standard interface for Long-Term Associative Recall (Gap 3).
    Enforces strict mathematical linkage between semantic searches and chronological event timelines.
    """
    
    @abstractmethod
    async def insert_episodic_node(self, record: VectorRecord) -> bool:
        """
        Saves a synthesized memory vector linked physically to a causal event.
        Ensures `causal_event_id` metadata indexing in target store (FAISS/Qdrant).
        """
        pass
        
    @abstractmethod
    async def search_related_episodes(
        self, 
        query_vector: List[float], 
        limit: int = 5,
        filter_workflow_id: Optional[str] = None
    ) -> List[VectorRecord]:
        """
        Queries semantic space, returning matching VectorRecords complete with 
        their ancestral event reference ids for chronological reconstruction.
        """
        pass
