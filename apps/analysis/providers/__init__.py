"""Provider registry: resolve a model id to its provider implementation."""
from .base import LLMProvider, UnknownModel
from .catalog import (
    DEFAULT_MODEL, MODELS, fallbacks_for, grouped_choices, pricing_for,
    provider_for,
)


def resolve_provider_for_model(model):
    """Return the provider key ('openai' / 'anthropic') for a model id.

    Raises UnknownModel for an unlisted id.
    """
    key = provider_for(model)
    if key is None:
        raise UnknownModel(f"No provider is registered for model {model!r}")
    return key


def get_provider(model, api_key=None):
    """Instantiate the LLMProvider that serves the given model id."""
    key = resolve_provider_for_model(model)
    if key == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=api_key)
    if key == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=api_key)
    raise UnknownModel(f"No provider implementation for {key!r}")  # pragma: no cover


__all__ = [
    "LLMProvider", "UnknownModel", "get_provider", "resolve_provider_for_model",
    "DEFAULT_MODEL", "MODELS", "fallbacks_for", "grouped_choices", "pricing_for",
    "provider_for",
]
