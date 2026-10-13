"""Model catalog: the single source of truth for which models exist, which
provider serves each, how they are priced, and the in-provider fallback order.

Pricing is ``(input_per_1M, output_per_1M)`` in USD, or ``None`` when the rate
has not been verified. Unknown pricing yields an estimated cost of ``0.0`` — we
never invent a number.

NOTE TO MAINTAINERS: fill in the Claude pricing tuples below with the current
published Anthropic rates. They are intentionally ``None`` until verified.
"""

# Ordered so the first entry is the global default (Claude Sonnet 5.5).
# Pricing reflects published rates at time of writing; verify before relying on
# the cost estimate. Unknown pricing (None) estimates 0.0 — never a fabricated number.
MODELS = [
    # id                 label                              provider      pricing (in, out) per 1M
    ("claude-sonnet-5-5", "Claude Sonnet 5.5 (Recommended)", "anthropic",  None),
    ("claude-opus-5-5",   "Claude Opus 5.5 (Most capable)",  "anthropic",  None),
    ("claude-haiku-5-5",  "Claude Haiku 5.5 (Fastest)",      "anthropic",  None),
    ("gpt-4.1",           "GPT-4.1",                          "openai",     (0.002, 0.008)),
    ("gpt-4.1-mini",      "GPT-4.1 mini",                     "openai",     (0.0004, 0.0016)),
    ("gpt-4o",            "GPT-4o",                           "openai",     (0.0025, 0.01)),
    ("gpt-4o-mini",       "GPT-4o mini (Faster)",             "openai",     (0.00015, 0.0006)),
]

DEFAULT_MODEL = MODELS[0][0]

_PROVIDER_BY_MODEL = {m[0]: m[2] for m in MODELS}
_PRICING_BY_MODEL = {m[0]: m[3] for m in MODELS}

# In-provider fallback order (never crosses providers / keys).
FALLBACKS = {
    "claude-sonnet-5-5": ["claude-sonnet-5-5", "claude-haiku-5-5"],
    "claude-opus-5-5": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"],
    "claude-haiku-5-5": ["claude-haiku-5-5"],
    "gpt-4.1": ["gpt-4.1", "gpt-4.1-mini", "gpt-4o"],
    "gpt-4.1-mini": ["gpt-4.1-mini", "gpt-4o-mini"],
    "gpt-4o": ["gpt-4o", "gpt-4o-mini"],
    "gpt-4o-mini": ["gpt-4o-mini"],
}


def provider_for(model):
    """Return the provider key for a model id, or None if unlisted."""
    return _PROVIDER_BY_MODEL.get(model)


def pricing_for(model):
    """Return (input, output) per-1M pricing tuple, or None if unknown."""
    return _PRICING_BY_MODEL.get(model)


def fallbacks_for(model):
    """Return the in-provider fallback model order for a model id."""
    return list(FALLBACKS.get(model, [model]))


def grouped_choices():
    """Return Django grouped choices: [(provider_label, [(id, label), ...]), ...]."""
    groups = {"anthropic": ("Claude (Anthropic)", []),
              "openai": ("OpenAI", [])}
    order = ["anthropic", "openai"]
    for mid, label, provider, _ in MODELS:
        groups.setdefault(provider, (provider.title(), []))
        groups[provider][1].append((mid, label))
    return [(groups[p][0], groups[p][1]) for p in order if groups.get(p) and groups[p][1]]
