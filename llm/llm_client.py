"""Gemini API connection. Model name and key come from the environment."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_MODEL = "gemini-3.8-flash"


class LLMError(RuntimeError):
    """Raised for any LLM configuration or API failure."""


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise LLMError(f"{name} must be a number, got {raw!r}") from exc


def _env_int(name: str, default: int) -> int:
    return int(_env_float(name, default))


@dataclass
class LLMConfig:
    api_key: Optional[str] = field(default=None, repr=False)
    model: str = DEFAULT_MODEL
    temperature: float = 0.1
    max_output_tokens: int = 2048

    @classmethod
    def from_env(cls) -> "LLMConfig":
        try:  # optional: pick up a local .env if python-dotenv is installed
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        return cls(
            api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            model=os.getenv("GEMINI_MODEL") or DEFAULT_MODEL,
            temperature=_env_float("GEMINI_TEMPERATURE", 0.1),
            max_output_tokens=_env_int("GEMINI_MAX_OUTPUT_TOKENS", 2048),
        )


class GeminiClient:
    """Thin wrapper around the google-genai SDK.

    The model is never substituted: if it is unavailable, calls raise LLMError.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig.from_env()
        self._sdk = None

    @property
    def model(self) -> str:
        return self.config.model

    def _client(self):
        if self._sdk is None:
            if not self.config.api_key:
                raise LLMError(
                    "Gemini API key not set. Define GEMINI_API_KEY in your environment/.env."
                )
            try:
                from google import genai
            except ImportError as exc:
                raise LLMError("google-genai is not installed: pip install google-genai") from exc
            self._sdk = genai.Client(api_key=self.config.api_key)
        return self._sdk

    def verify_model(self) -> bool:
        """Confirm the configured model is reachable with this key. Raises LLMError if not."""
        try:
            self._client().models.get(model=self.config.model)
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Model '{self.config.model}' not available via Gemini API: {exc}") from exc
        return True

    def generate(self, prompt: str, system_instruction: str) -> str:
        client = self._client()
        try:
            from google.genai import types

            response = client.models.generate_content(
                model=self.config.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=self.config.temperature,
                    max_output_tokens=self.config.max_output_tokens,
                ),
            )
        except Exception as exc:
            raise LLMError(f"Gemini request failed for model '{self.config.model}': {exc}") from exc

        text = getattr(response, "text", None)
        if not text or not text.strip():
            raise LLMError("Gemini returned an empty response (possibly blocked or truncated).")
        return text.strip()
