import os
import json
import httpx
from typing import Dict, Any, Optional
from lifeline.adapters.llm.base import BaseLLMAdapter
from lifeline.core.exceptions import CognitiveParsingError

class GeminiAdapter(BaseLLMAdapter):
    """
    High-Performance production LLM Adapter for Google Gemini.
    Operates via raw HTTP REST calling asynchronously to avoid SDK dependency weight.
    Implements Strict Structural Parsing Locks.
    """
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    async def generate_structured_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        response_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Direct REST invocation forcing Application/JSON using native Gemini response_schema capabilities.
        """
        if not self.api_key:
            raise RuntimeError("CRITICAL CONFIGURATION ERROR: GEMINI_API_KEY environment variable is missing.")

        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}

        # Construct canonical Gemini API Payload
        payload: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1 # Ensure maximum determinism
            }
        }

        if system_instruction:
            payload["system_instruction"] = {
                "parts": [{"text": system_instruction}]
            }

        if response_schema:
            # Map responseSchema to standard OpenAPI schema requested by Gemini
            payload["generationConfig"]["responseSchema"] = response_schema

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    params=params,
                    json=payload
                )
                
                if response.status_code != 200:
                    err_text = response.text
                    raise RuntimeError(f"Gemini API returned status {response.status_code}: {err_text}")
                
                res_data = response.json()
        except httpx.RequestError as http_err:
            raise RuntimeError(f"Physical Network Collision communicating with Gemini: {str(http_err)}")

        # 1. Extraction Boundary
        try:
            candidates = res_data.get("candidates", [])
            if not candidates:
                raise CognitiveParsingError("Gemini API returned empty candidate list (Blocked / Refusal)")
            
            raw_content = candidates[0].get("content", {}).get("parts", [])[0].get("text", "")
            if not raw_content:
                 raise CognitiveParsingError("Extracted content text was null or empty")
        except (KeyError, IndexError) as exc:
            raise CognitiveParsingError(f"Failed parsing Gemini's response envelope structure: {str(exc)}")

        # 2. Strict Structural Parsing Lock (Fail-Fast)
        try:
            structured_data = json.loads(raw_content.strip())
        except json.JSONDecodeError as json_err:
            raise CognitiveParsingError(
                f"STRUCTURAL LOCK VIOLATION: Raw output not valid JSON. Trace: {str(json_err)}. Raw output: '{raw_content}'"
            )

        # 3. Semantic Schema Enforcement
        if response_schema and "required" in response_schema:
            required_keys = response_schema["required"]
            missing_keys = [key for key in required_keys if key not in structured_data]
            if missing_keys:
                raise CognitiveParsingError(
                    f"SCHEMA CONSTRAINT VIOLATION: Model output missing required keys {missing_keys}. Output keys: {list(structured_data.keys())}"
                )

        return structured_data
