"""Anthropic (Claude) provider implementing the standard completion contract.

Claude's Messages API differs from OpenAI's chat completions in two ways we
adapt here:

- The system prompt is a top-level ``system`` argument, not a message with
  ``role="system"``. We lift it out of ``messages``.
- Usage is reported as ``input_tokens`` / ``output_tokens`` (no total); we map
  them to prompt / completion / total.

Claude has no ``response_format`` switch, so JSON output is requested in the
prompt (the service already asks for a single JSON object). ``response_format``
is accepted and ignored for a uniform caller contract.
"""
import logging
import os
import time

from .base import LLMProvider
from .catalog import pricing_for

logger = logging.getLogger(__name__)

# Claude requires an explicit max_tokens; use a sane default matching the
# service's OpenAI call budget.
_DEFAULT_MAX_TOKENS = 2500


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No Anthropic API key provided. Set ANTHROPIC_API_KEY or add one "
                "to your profile."
            )
        try:
            from anthropic import Anthropic
        except ImportError as exc:  # pragma: no cover - import guard
            raise ImportError(
                "anthropic library is not installed. Install it with "
                "'pip install anthropic'."
            ) from exc
        self._client = Anthropic(api_key=self.api_key)

    def _create(self, **params):
        """Perform the actual API call. Isolated so it can be mocked in tests."""
        return self._client.messages.create(**params)

    def chat_completion(self, model, messages, temperature=0.2,
                        max_tokens=None, response_format=None, **kwargs):
        start_time = time.time()

        # Lift the system message(s) out; keep the rest as user/assistant turns.
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        convo = [m for m in messages if m.get("role") != "system"]

        params = {
            "model": model,
            "messages": convo,
            "max_tokens": max_tokens or _DEFAULT_MAX_TOKENS,
            "temperature": temperature,
        }
        if system_parts:
            params["system"] = "\n\n".join(system_parts)

        try:
            response = self._create(**params)
        except Exception as exc:
            logger.error("Anthropic API call failed: %s", exc)
            raise

        content = "".join(
            block.text for block in response.content
            if getattr(block, "type", None) == "text"
        )
        usage = response.usage
        prompt_tokens = getattr(usage, "input_tokens", 0) or 0
        completion_tokens = getattr(usage, "output_tokens", 0) or 0
        return {
            "content": content,
            "tokens": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "model": model,
            "elapsed_time": time.time() - start_time,
        }

    def calculate_cost(self, model, tokens):
        rate = pricing_for(model)
        if rate is None:
            return 0.0
        input_rate, output_rate = rate
        return (
            (tokens.get("prompt_tokens", 0) / 1_000_000) * input_rate
            + (tokens.get("completion_tokens", 0) / 1_000_000) * output_rate
        )
