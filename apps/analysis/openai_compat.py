"""
OpenAI client wrapper.

A thin wrapper around the OpenAI Python SDK (>= 1.x) that exposes a small,
stable surface to the rest of the app: ``chat_completion`` returns a plain
dict regardless of SDK internals, and ``calculate_cost`` estimates spend.

No API key is ever written to disk and no generated code is executed; on
failure the underlying exception propagates to the caller, which owns the
retry/fallback policy.
"""
import logging
import os
import time

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Compatibility wrapper for the OpenAI chat completions API (SDK >= 1.x)."""

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No API key provided. Set OPENAI_API_KEY or pass api_key."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - import guard
            raise ImportError(
                "OpenAI library is not installed. Install it with 'pip install openai'."
            ) from exc
        self._client = OpenAI(api_key=self.api_key)

    def _create(self, **params):
        """Perform the actual API call. Isolated so it can be mocked in tests."""
        return self._client.chat.completions.create(**params)

    def chat_completion(
        self,
        model,
        messages,
        temperature=0.2,
        max_tokens=None,
        response_format=None,
        **kwargs,
    ):
        """
        Create a chat completion and return a standardized response dict.

        Returns:
            {
                "content": str,
                "tokens": {"prompt_tokens", "completion_tokens", "total_tokens"},
                "model": str,
                "elapsed_time": float,
            }
        """
        start_time = time.time()

        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if response_format is not None:
            params["response_format"] = response_format
        for key, value in kwargs.items():
            if key not in params:
                params[key] = value

        try:
            response = self._create(**params)
        except Exception as exc:
            # Some models (e.g. base gpt-4) don't support JSON response_format.
            # Fall back once to a plain call and rely on the prompt to ask for
            # JSON, rather than failing the whole analysis.
            if response_format is not None and "response_format" in str(exc).lower():
                logger.warning(
                    "Model %s rejected response_format; retrying without it: %s",
                    model, exc,
                )
                params.pop("response_format", None)
                response = self._create(**params)
            else:
                logger.error("OpenAI API call failed: %s", exc)
                raise

        content = response.choices[0].message.content
        usage = response.usage
        return {
            "content": content,
            "tokens": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            },
            "model": model,
            "elapsed_time": time.time() - start_time,
        }

    def calculate_cost(self, model, tokens):
        """Estimate the cost (USD) of a call given a token-count dict."""
        # Pricing per 1M tokens (input, output).
        model_pricing = {
            "gpt-3.5-turbo": (0.0005, 0.0015),
            "gpt-4": (0.03, 0.06),
            "gpt-4-turbo": (0.01, 0.03),
            "gpt-4o": (0.0025, 0.01),
        }
        if model in model_pricing:
            input_rate, output_rate = model_pricing[model]
            return (
                (tokens.get("prompt_tokens", 0) / 1_000_000) * input_rate
                + (tokens.get("completion_tokens", 0) / 1_000_000) * output_rate
            )
        return (tokens.get("total_tokens", 0) / 1_000_000) * 0.02
