"""Thin wrapper around the google-genai SDK (retries, usage, latency)."""
import os
import time
from dataclasses import dataclass

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")


@dataclass
class LLMResult:
    text: str
    model: str
    latency_s: float
    prompt_tokens: int | None = None
    output_tokens: int | None = None


class GeminiClient:
    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None,
                 temperature: float = 0.1, max_output_tokens: int = 1024, retries: int = 3):
        from google import genai  # pip install google-genai
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("Set GEMINI_API_KEY (get one at https://aistudio.google.com/apikey)")
        self._genai = genai
        self.client = genai.Client(api_key=key)
        self.model, self.temperature, self.max_output_tokens, self.retries = model, temperature, max_output_tokens, retries

    def generate(self, prompt: str, system: str | None = None, json_output: bool = False) -> LLMResult:
        from google.genai import types
        cfg = types.GenerateContentConfig(
            system_instruction=system, temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            response_mime_type="application/json" if json_output else None)
        last = None
        for attempt in range(self.retries):
            t0 = time.time()
            try:
                r = self.client.models.generate_content(model=self.model, contents=prompt, config=cfg)
                u = getattr(r, "usage_metadata", None)
                return LLMResult(r.text or "", self.model, time.time() - t0,
                                 getattr(u, "prompt_token_count", None), getattr(u, "candidates_token_count", None))
            except Exception as e:  # rate limit / transient
                last = e
                time.sleep(2 ** attempt)
        raise RuntimeError(f"Gemini call failed after {self.retries} tries: {last}")
