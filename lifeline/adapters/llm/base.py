from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseLLMAdapter(ABC):
    """
    Abstract architectural boundary separating raw Cognitive Intel Providers (Gemini, Anthropic, etc.)
    from Lifeline Core Engines.
    """
    @abstractmethod
    async def generate_structured_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        response_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Forces the target LLM provider to return structurally sound JSON payloads matching
        the provided schema boundaries.
        
        Raises:
            CognitiveParsingError: If response is malformed or fails schema assertions.
            RuntimeError: On connection / rate-limit failures.
        """
        pass
