# P1 Design — Multi-Provider Analysis + Result Caching

**Date:** 2026-10-13
**Branch:** `p1-multiprovider-caching`
**Status:** Spec for review
**Predecessor:** Sprint 1 (`docs/superpowers/specs/2026-10-12-sprint1-analysis-diff-ux-design.md`)

## Goal / Intent

Phase P1 of the post-Sprint-1 roadmap deepens **analysis quality**. This slice
delivers two of P1's three sub-features:

1. **Multi-provider LLM support** — the analysis engine, hard-wired to OpenAI,
   becomes provider-pluggable. Ship OpenAI **and** Anthropic Claude, with Claude
   the default. The interface is designed so a third provider is a new file, not
   a refactor.
2. **Result caching** — re-requesting an analysis for an unchanged advisory with
   the same provider/model no longer re-spends tokens: the stored result is
   reused. "Regenerate" remains the explicit way to force a fresh call.

Deferred to **P1-followup** (noted, not built here): CWE→CVE / NVD enrichment.

### Success criteria

- A new analysis can be run against either OpenAI or Claude, chosen per analysis
  from one model dropdown; Claude (Sonnet 5.5) is the default.
- Provider API keys resolve from the user profile first, then env/settings.
- Submitting "create analysis" for an advisory whose inputs, provider, model, and
  prompt version are unchanged reuses the existing `Analysis` (no LLM call) and
  tells the user so; "Regenerate" always re-runs.
- Everything degrades gracefully with no key for the chosen provider (clear
  message, no crash), consistent with Sprint 1.
- No secrets written to disk; no code-eval paths (unchanged from Sprint 1).

## Global Constraints

- **Python 3.10** interpreter (`venv310/bin/python`); never the shadowed global.
- **Migrations are disabled** (`MIGRATION_MODULES=None`); schema is applied via
  `migrate --run-syncdb`, which creates missing *tables* but not new *columns* on
  existing tables. New columns MUST be nullable or defaulted, and the dev sqlite
  DB needs a one-off `ALTER TABLE` per new column (same ruling as Sprint 1).
- **`httpx==0.27.2`** is pinned (openai 1.51.0 vs httpx ≥ 0.28 `proxies`). Any new
  dependency (the `anthropic` SDK) MUST be compatible with this pin.
- Pin every new dependency to an exact version at least two weeks old.
- Caller contract for a completion is unchanged: a dict
  `{content, tokens: {prompt_tokens, completion_tokens, total_tokens}, model, elapsed_time}`.
- Test runner is Django `manage.py test` (no pytest); TDD RED→GREEN per task.
- Project name is POCanator; no reintroduction of legacy branding.

## Review Focus

Input classes / failure modes the design implies that the happy-path tests would
not catch — each gets a test in the owning task:

1. **Claude returns non-JSON** (no `response_format` to force it) → must flow
   through the same `json.loads → None` graceful path as OpenAI, yielding a
   failed-analysis message, not a 500. (Task 3 / Task 5)
2. **Key for the chosen provider is missing** (e.g. user has an OpenAI key but
   picks a Claude model, and no env Claude key) → clear user-facing error, no
   crash, no analysis row. (Task 6)
3. **Same advisory, different provider/model** → different fingerprint, so no
   false cache hit returning another provider's result. (Task 4)
4. **Advisory with no commits** (empty patch text) → fingerprint is still
   deterministic and caching still works. (Task 4)
5. **`anthropic` SDK vs pinned `httpx==0.27.2`** → the pin must hold; if the SDK
   needs a newer httpx, that is a blocking finding to surface, not silently
   bump. (Task 1)

## Current State (as read 2026-10-13)

- `apps/analysis/services.py` → `AnalysisService.__init__` builds an
  `OpenAIClient` directly (`self.openai_client`); `analyze_advisory` iterates a
  hard-coded OpenAI fallback list (`gpt-4o → gpt-4-turbo → gpt-3.5-turbo`), calls
  `chat_completion(..., response_format={"type":"json_object"})`, parses JSON via
  `_parse_analysis_results` (returns `None` on bad JSON), and on success creates
  an `Analysis`. Cost comes from `self.openai_client.calculate_cost(model, tokens_dict)`.
- `apps/analysis/openai_compat.py` → `OpenAIClient` (SDK ≥ 1.x): `chat_completion`
  returns the standard dict and retries once without `response_format` if a model
  rejects it; `calculate_cost(model, tokens_dict)` holds the OpenAI pricing table.
- `apps/analysis/forms.py` → `CreateAnalysisForm.MODEL_CHOICES` is three OpenAI
  models; default `gpt-4o`.
- `apps/analysis/views.py` → `CreateAnalysisView.post` resolves
  `request.user.profile.openai_api_key`, calls the service, redirects to detail;
  `RegenerateAnalysisView.post` re-runs with `model=analysis.model_used` and
  deletes the prior row on success.
- `apps/analysis/models.py` → `Analysis` has `model_used`, `vuln_type`,
  `severity`, `cwe`, `confidence`, `tokens_used`, `estimated_cost`, scores, etc.
- `apps/users/models.py` → `UserProfile` has `openai_api_key`, `github_token`,
  `default_model`; `apps/users/forms.py` edits those three.
- No `CACHES` configured and no cache usage anywhere.

## Approach Decision

**Providers — chosen: a thin `LLMProvider` abstraction + registry.** The existing
`OpenAIClient` is wrapped by an `OpenAIProvider` (zero behavior change, so Sprint 1
tests stand); a new `AnthropicProvider` implements the same contract over the
Claude Messages API. A `catalog.py` maps model → provider and holds pricing and
per-provider fallback chains. Rejected: (a) a giant `if provider == ...` inside the
service — spreads provider logic across the service and resists a third provider;
(b) LangChain/LiteLLM — a heavy dependency for two providers and a fixed call shape.

**Caching — chosen: domain-level reuse via a content fingerprint on `Analysis`**
(approach A from brainstorming). The result is already persisted as an `Analysis`
row; a `fingerprint` column lets a repeat create reuse it. Invalidation is
content-addressed and free — change the advisory/patch, the model, the provider,
or the prompt version and the fingerprint differs, so it re-runs. Rejected: a
Django cache backend + TTL — duplicate storage of a response already in the DB,
plus TTL tuning and (for local-memory) no persistence across restarts.

## Scope — Work Items

### 1. The `anthropic` dependency + provider base contract
- Add `anthropic` (exact pin, ≥ 2 weeks old) to `requirements.txt`; verify it
  installs under the pinned `httpx==0.27.2` in `venv310`. If it cannot, STOP and
  surface it (Review Focus 5) — do not bump httpx without a decision.
- `providers/base.py`: `LLMProvider` ABC with `name`, `chat_completion(...)` (the
  standard-dict contract), and `calculate_cost(model, tokens)`.

### 2. Provider registry + model catalog
- `providers/catalog.py`: `MODELS` — an ordered list of
  `{id, label, provider, pricing}` where `pricing` is `(input_per_1m, output_per_1m)`
  or `None` when unverified. Claude ids `claude-sonnet-5-5` (default),
  `claude-opus-5-5`, `claude-haiku-5-5`; OpenAI ids `gpt-4o`, `gpt-4-turbo`,
  `gpt-3.5-turbo`. Per-provider `FALLBACKS` map a model to an in-provider fallback
  order. **Claude pricing left as a clearly-marked maintainer TODO; `None` pricing
  yields `estimated_cost == 0.0`, never a fabricated number.**
- `providers/__init__.py`: `resolve_provider_for_model(model) -> "openai"|"anthropic"`
  (raises `UnknownModel` for an unlisted id) and
  `get_provider(model, api_key) -> LLMProvider`.

### 3. OpenAIProvider + AnthropicProvider
- `providers/openai_provider.py`: wraps the existing `OpenAIClient` unchanged;
  `calculate_cost` delegates to it.
- `providers/anthropic_provider.py`: constructs `anthropic.Anthropic(api_key=...)`;
  `chat_completion` splits the `system` message out of `messages`, calls
  `messages.create(model, system=, messages=, max_tokens, temperature)`, and maps
  `usage.input_tokens/output_tokens → prompt/completion/total`; `response_format`
  is accepted and ignored (JSON is requested in the prompt). `calculate_cost` uses
  the catalog pricing (→ `0.0` when `None`). Missing key raises a `ValueError`
  with a clear message (same shape as `OpenAIClient`).

### 4. Fingerprint + cache reuse in the service
- `services.py`: add `PROMPT_VERSION` constant. Add
  `_fingerprint(provider, model, system_prompt, prompt) -> sha256 hex`.
- `AnalysisService` resolves the provider via `get_provider` instead of building
  `OpenAIClient`; the fallback list comes from the catalog for the chosen
  provider (no cross-provider fallback).
- `analyze_advisory(advisory, model=..., use_cache=True)`: build prompt + system
  prompt, compute fingerprint; if `use_cache` and an `Analysis` with that
  fingerprint exists, return it with a transient `was_cached = True` and **no LLM
  call**. Otherwise call the provider, parse, and create the row with `fingerprint`
  and `provider` set, `was_cached = False`.
- Default `model` becomes the catalog default (Sonnet 5.5) rather than `gpt-4o`.

### 5. Model + key fields, forms, settings
- `Analysis`: add `fingerprint` (CharField, db_index, default `""`) and `provider`
  (CharField, default `""`). `UserProfile`: add `anthropic_api_key` (nullable
  CharField, mirrors `openai_api_key`). Dev DB `ALTER TABLE` for all three.
- `settings`: `ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")`.
- `CreateAnalysisForm`: model field choices built from the catalog, **grouped by
  provider** (Django grouped choices), default = catalog default.
- `UserProfileForm`: add `anthropic_api_key` to fields.

### 6. Views: key resolution per provider + cache-hit notice
- A helper resolving the API key for a model's provider: user profile
  (`openai_api_key` / `anthropic_api_key`) → `settings`. Used by
  `CreateAnalysisView` and `RegenerateAnalysisView`.
- `CreateAnalysisView.post`: after a successful analysis, if `was_cached`, add an
  info message *"Existing analysis from `<created_at>` reused — Regenerate to
  refresh."*; else the usual success message.
- `RegenerateAnalysisView.post`: pass `use_cache=False` so it always re-runs
  (keeps its replace-the-old-row behavior).
- Missing-key path: service returns `None`; the view shows the existing
  failure message naming the provider.

## Data Flow

```
create form (model) ─▶ view resolves key for model's provider
   └▶ AnalysisService.analyze_advisory(advisory, model, use_cache=True)
        ├─ build system_prompt + prompt
        ├─ fingerprint = sha256(PROMPT_VERSION|provider|model|system_prompt|prompt)
        ├─ if use_cache and Analysis(fingerprint=…) exists ─▶ return it (was_cached=True)   [no API call]
        └─ else get_provider(model, key).chat_completion(...) ─▶ parse JSON
               ├─ None  ─▶ failed-analysis message
               └─ data  ─▶ create Analysis(fingerprint, provider, cost=provider.calculate_cost(...))
view ─▶ redirect to detail;  was_cached ? "reused" notice : "created" notice
Regenerate ─▶ analyze_advisory(use_cache=False) ─▶ always calls provider ─▶ replaces prior row
```

## Testing Strategy

Django `TestCase`, TDD. Per task: registry resolution + `UnknownModel`;
OpenAIProvider delegates to `OpenAIClient` (contract dict); AnthropicProvider maps
a mocked SDK response (system split, token mapping, cost via catalog / `0.0` when
unpriced); `_fingerprint` deterministic and sensitive to provider/model/prompt;
**cache hit returns the existing row with `chat_completion` asserted not called**;
regenerate (`use_cache=False`) calls the provider and replaces; form default is
Sonnet 5.5 and choices include both providers grouped; key resolution prefers the
user profile over env; missing provider key → graceful `None`. The Sprint 1
requirements-lint test continues to assert every line (incl. `anthropic`) parses.

## Backlog (unchanged, minus what ships here)

CWE→CVE/NVD enrichment (P1-followup) · background/Celery batch analysis (P3) ·
side-by-side diff (P2) · auth + production hardening / deploy pipeline (P4) ·
CLI/web env-var unification (P4).
