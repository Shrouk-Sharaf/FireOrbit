"""FireOrbit LLM layer: grounded answer generation over retrieved chunks.

This package only *consumes* retrieval output. It does not chunk, embed,
search, or store anything.
"""
from .generator import generate_answer
from .llm_client import GeminiClient, LLMConfig, LLMError

__all__ = ["generate_answer", "GeminiClient", "LLMConfig", "LLMError"]
