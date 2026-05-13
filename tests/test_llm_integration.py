import unittest
import asyncio
import json
from unittest.mock import patch, AsyncMock
import httpx

from lifeline.core.exceptions import CognitiveParsingError
from lifeline.adapters.llm.gemini_adapter import GeminiAdapter
from lifeline.context.compression import ContextCompressionEngine, ContextBudget
from lifeline.core.events import FailureEvent, SystemEvent

class TestLLMIntegration(unittest.IsolatedAsyncioTestCase):
    """
    Validates Hybrid Cognition Layer safeguards, including parsing locks,
    HTTP connectivity mocks, and Context budget protection shield.
    """
    def setUp(self):
        self.api_key = "test-api-key"
        self.adapter = GeminiAdapter(api_key=self.api_key)
        self.compression_engine = ContextCompressionEngine(
            budget=ContextBudget(max_events=10, max_failures=3, max_character_budget=5000)
        )

    async def test_adapter_successful_json_parsing(self):
        """Asserts that fully compliant REST response passes Structural Parsing Lock."""
        mock_response_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": '{"fix_code": "def execute(): return True", "confidence": 0.95}'}
                        ]
                    }
                }
            ]
        }
        
        schema = {
            "type": "object",
            "properties": {
                "fix_code": {"type": "string"},
                "confidence": {"type": "number"}
            },
            "required": ["fix_code", "confidence"]
        }
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = AsyncMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_payload
            mock_post.return_value = mock_response
            
            result = await self.adapter.generate_structured_content(
                prompt="Generate a fix.",
                system_instruction="Strictly JSON.",
                response_schema=schema
            )
            
            self.assertEqual(result["confidence"], 0.95)
            self.assertIn("def execute", result["fix_code"])

    async def test_adapter_structural_parsing_lock_malformed_json(self):
        """Asserts CognitiveParsingError is raised when raw model content is corrupt JSON."""
        mock_response_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "{'broken_json': true, dangling_bracket"}
                        ]
                    }
                }
            ]
        }
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = AsyncMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_payload
            mock_post.return_value = mock_response
            
            with self.assertRaises(CognitiveParsingError) as context:
                await self.adapter.generate_structured_content("Make plan")
                
            self.assertIn("STRUCTURAL LOCK VIOLATION", str(context.exception))

    async def test_adapter_schema_constraint_violation(self):
        """Asserts CognitiveParsingError is raised when required schema keys are missing."""
        mock_response_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": '{"invented_key": "hallucinated output"}'}
                        ]
                    }
                }
            ]
        }
        
        schema = {
            "type": "object",
            "required": ["mandatory_key"]
        }
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = AsyncMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_payload
            mock_post.return_value = mock_response
            
            with self.assertRaises(CognitiveParsingError) as context:
                await self.adapter.generate_structured_content("Produce mandatory_key", response_schema=schema)
                
            self.assertIn("SCHEMA CONSTRAINT VIOLATION", str(context.exception))

    def test_semantic_context_compression_collapsing(self):
        """
        Shield Verification: Verifies multiple consecutive cognitive FailureEvents 
        are collapsed into a single analytical summary.
        """
        # Build a sequence of events:
        # 1. SystemEvent (Success)
        # 2. FailureEvent (Cognitive) - Attempt 1
        # 3. FailureEvent (Cognitive) - Attempt 2
        # 4. FailureEvent (Cognitive) - Attempt 3
        # 5. SystemEvent (Final retry prompt)
        
        ev_1 = SystemEvent(action="TASK_SPAWNED", workflow_id="wf_1")
        ev_1.seal(parent_hashes=[], logical_clock=1)
        
        f_1 = FailureEvent(
            workflow_id="wf_1", 
            failure_domain="COGNITIVE", 
            error_message="JSON parse error 1",
            stack_trace="trace 1"
        )
        f_1.seal(parent_hashes=[ev_1.event_id], logical_clock=2)
        
        f_2 = FailureEvent(
            workflow_id="wf_1", 
            failure_domain="COGNITIVE", 
            error_message="JSON schema violation 2",
            stack_trace="trace 2"
        )
        f_2.seal(parent_hashes=[f_1.event_id], logical_clock=3)

        f_3 = FailureEvent(
            workflow_id="wf_1", 
            failure_domain="COGNITIVE", 
            error_message="Timeout on schema 3",
            stack_trace="trace 3"
        )
        f_3.seal(parent_hashes=[f_2.event_id], logical_clock=4)

        ev_last = SystemEvent(action="PREPARING_LAST_RETRY", workflow_id="wf_1")
        ev_last.seal(parent_hashes=[f_3.event_id], logical_clock=5)
        
        # Create scored fragments (as ranker would produce, e.g., sorted by high score)
        raw_fragments = [
            {"event": ev_1, "score": 0.9},
            {"event": f_1, "score": 0.5},
            {"event": f_2, "score": 0.6},
            {"event": f_3, "score": 0.7},
            {"event": ev_last, "score": 0.95}
        ]
        
        reconstructed_state = {"current_phase": "reparation"}
        
        # Compress payload!
        compressed = self.compression_engine.compress(raw_fragments, reconstructed_state)
        
        # Expectations:
        # - The 3 consecutive FailureEvents must collapse into 1 synthetic FailureEvent!
        # - Length of returned array should be 3 (ev_1, synthetic_collapsed_failure, ev_last)
        self.assertEqual(len(compressed), 3, "Context compression failed to collapse cognitive failures!")
        
        # Assert chronological sequence remains correct
        events_seq = [x["event"] for x in compressed]
        
        self.assertEqual(events_seq[0].action, "TASK_SPAWNED")
        self.assertEqual(events_seq[2].action, "PREPARING_LAST_RETRY")
        
        # Assert the middle synthetic event collapsed data correctly
        summary_event = events_seq[1]
        self.assertTrue(isinstance(summary_event, FailureEvent))
        self.assertEqual(summary_event.failure_domain, "COGNITIVE")
        self.assertIn("[BUDGET SHIELD COLLAPSE]", summary_event.error_message)
        self.assertIn("3-attempt failure loop", summary_event.error_message)
        self.assertIn("Timeout on schema 3", summary_event.error_message) # Inherits latest msg
        self.assertIn("conserve context bytes", summary_event.stack_trace) # Truncated traces

if __name__ == "__main__":
    unittest.main()
