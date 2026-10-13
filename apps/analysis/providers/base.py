"""Provider abstraction for LLM chat completions.

Every provider returns the same standardized dict so the rest of the app never
depends on a particular SDK:

    {
        "content": str,
        "tokens": {"prompt_tokens", "completion_tokens", "total_tokens"},
        "model": str,
        "elapsed_time": float,
    }
"""
from abc import ABC, abstractmethod


class UnknownModel(ValueError):
    """Raised when a model id maps to no registered provider."""


class LLMProvider(ABC):
    """Common interface implemented by each concrete provider."""

    #: short provider key, e.g. "openai" / "anthropic"
    name = ""

    @abstractmethod
    def chat_completion(self, model, messages, temperature=0.2,
                        max_tokens=None, response_format=None, **kwargs):
        """Create a chat completion and return the standardized response dict."""
        raise NotImplementedError

    @abstractmethod
    def calculate_cost(self, model, tokens):
        """Estimate cost (USD) for a call given a token-count dict.

        Returns ``0.0`` when pricing for the model is unknown — never a
        fabricated number.
        """
        raise NotImplementedError
