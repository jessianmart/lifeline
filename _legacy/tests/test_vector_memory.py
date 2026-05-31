import unittest
from lifeline.context.memory import VectorRecord
from lifeline.context.local import LocalVectorMemory
from lifeline.memory.semantic import SemanticMemory
from lifeline.context.retrieval import FederatedContextRetrieval
from lifeline.adapters.storage.sqlite import SQLiteEventStore
from lifeline.engines.event_engine import EventEngine
from lifeline.engines.state_engine import StateEngine
import os

class TestVectorMemory(unittest.IsolatedAsyncioTestCase):
    async def test_dimension_enforcement(self):
        # Local memory with dimension = 3
        memory = LocalVectorMemory(embedding_dimension=3)
        
        # Valid insertion
        valid_rec = VectorRecord(
            vector=[1.0, 2.0, 3.0],
            payload_text="Valid 3D record",
            causal_event_id="ev_001",
            metadata={"workflow_id": "wf_test"}
        )
        success = await memory.insert_episodic_node(valid_rec)
        self.assertTrue(success)
        
        # Invalid insertion (dimension = 4)
        invalid_rec = VectorRecord(
            vector=[1.0, 2.0, 3.0, 4.0],
            payload_text="Invalid 4D record",
            causal_event_id="ev_002",
            metadata={"workflow_id": "wf_test"}
        )
        with self.assertRaises(ValueError) as context:
            await memory.insert_episodic_node(invalid_rec)
        self.assertIn("Dimension Mismatch", str(context.exception))

    async def test_cosine_similarity_accuracy(self):
        memory = LocalVectorMemory(embedding_dimension=3)
        
        rec1 = VectorRecord(
            vector=[1.0, 0.0, 0.0],
            payload_text="X-axis unit vector",
            causal_event_id="ev_x",
            metadata={"workflow_id": "wf_1"}
        )
        rec2 = VectorRecord(
            vector=[0.0, 1.0, 0.0],
            payload_text="Y-axis unit vector",
            causal_event_id="ev_y",
            metadata={"workflow_id": "wf_1"}
        )
        rec3 = VectorRecord(
            vector=[1.0, 1.0, 0.0],
            payload_text="Diagonal vector in XY plane",
            causal_event_id="ev_diag",
            metadata={"workflow_id": "wf_2"}
        )
        
        await memory.insert_episodic_node(rec1)
        await memory.insert_episodic_node(rec2)
        await memory.insert_episodic_node(rec3)
        
        # Querying with a vector close to X axis: [0.9, 0.1, 0.0]
        results = await memory.search_related_episodes([0.9, 0.1, 0.0], limit=2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].causal_event_id, "ev_x")
        self.assertEqual(results[1].causal_event_id, "ev_diag")

        # Querying with filter_workflow_id = "wf_2"
        wf_results = await memory.search_related_episodes(
            [0.9, 0.1, 0.0], 
            limit=5, 
            filter_workflow_id="wf_2"
        )
        self.assertEqual(len(wf_results), 1)
        self.assertEqual(wf_results[0].causal_event_id, "ev_diag")

    async def test_federated_retrieval_integration(self):
        db_path = "test_temp_retrieval.db"
        if os.path.exists(db_path):
            try: os.remove(db_path)
            except: pass
            
        store = SQLiteEventStore(db_path)
        await store.initialize()
        event_engine = EventEngine(store)
        state_engine = StateEngine(event_engine)
        
        # Vector memory mock with 3 dimensions
        vector_mem = LocalVectorMemory(embedding_dimension=3)
        await vector_mem.insert_episodic_node(VectorRecord(
            vector=[0.8, 0.6, 0.0],
            payload_text="Important log",
            causal_event_id="event_target",
            metadata={"workflow_id": "wf_test"}
        ))
        
        retrieval = FederatedContextRetrieval(
            store=store, 
            event_engine=event_engine, 
            state_engine=state_engine,
            vector_memory=vector_mem
        )
        
        # Pull context without vector query
        ctx = await retrieval.retrieve_raw_context("wf_test")
        self.assertIn("semantic_memory", ctx)
        self.assertEqual(len(ctx["semantic_memory"]), 0)
        
        # Pull context WITH vector query
        ctx_with_vector = await retrieval.retrieve_raw_context(
            "wf_test", 
            query_vector=[0.8, 0.6, 0.0]
        )
        self.assertEqual(len(ctx_with_vector["semantic_memory"]), 1)
        self.assertEqual(ctx_with_vector["semantic_memory"][0]["causal_event_id"], "event_target")
        self.assertEqual(ctx_with_vector["semantic_memory"][0]["payload_text"], "Important log")
        
        # Clean up database
        if os.path.exists(db_path):
            try: os.remove(db_path)
            except: pass

    async def test_vector_memory_persistence(self):
        persist_file = "test_vectors_persistence.json"
        if os.path.exists(persist_file):
            try: os.remove(persist_file)
            except: pass
            
        try:
            # 1. Initialize persistent memory and insert record
            memory1 = LocalVectorMemory(embedding_dimension=3, persistence_path=persist_file)
            rec = VectorRecord(
                vector=[1.0, 0.0, 0.0],
                payload_text="Persistent unit vector",
                causal_event_id="ev_persisted",
                metadata={"workflow_id": "wf_persist"}
            )
            await memory1.insert_episodic_node(rec)
            
            # Check file was created
            self.assertTrue(os.path.exists(persist_file))
            
            # 2. Re-instantiate memory from the same path
            memory2 = LocalVectorMemory(embedding_dimension=3, persistence_path=persist_file)
            self.assertEqual(len(memory2._records), 1)
            self.assertEqual(memory2._records[0].causal_event_id, "ev_persisted")
            self.assertEqual(memory2._records[0].payload_text, "Persistent unit vector")
            self.assertEqual(memory2._records[0].vector, [1.0, 0.0, 0.0])
            
        finally:
            if os.path.exists(persist_file):
                try: os.remove(persist_file)
                except: pass

if __name__ == "__main__":
    unittest.main()
