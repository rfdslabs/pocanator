"""OpenAI provider — a thin wrapper over the existing OpenAIClient so Sprint 1
behavior (response_format retry, no key -> ValueError) is preserved verbatim.
"""
from .base import LLMProvider
from .catalog import pricing_for
from ..openai_compat import OpenAIClient


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key=None):
        # OpenAIClient raises ValueError when no key is available.
        self._client = OpenAIClient(api_key=api_key)

    def chat_completion(self, model, messages, temperature=0.2,
                        max_tokens=None, response_format=None, **kwargs):
        return self._client.chat_completion(
            model=model, messages=messages, temperature=temperature,
            max_tokens=max_tokens, response_format=response_format, **kwargs,
        )

    def calculate_cost(self, model, tokens):
        # Prefer the catalog (single source of truth); fall back to the client's
        # own table for models the catalog may not price.
        rate = pricing_for(model)
        if rate is None:
            return self._client.calculate_cost(model, tokens)
        input_rate, output_rate = rate
        return (
            (tokens.get("prompt_tokens", 0) / 1_000_000) * input_rate
            + (tokens.get("completion_tokens", 0) / 1_000_000) * output_rate
        )
