# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### P1 — Multi-provider analysis + result caching

#### Added
- **Pluggable LLM providers** (`apps/analysis/providers/`): a thin `LLMProvider`
  interface with a model catalog, serving **OpenAI and Anthropic Claude**. The
  model is chosen per analysis from one grouped dropdown; the provider is
  inferred from the model. Claude **Sonnet 5.5** is the default. Adding a third
  provider is a new file, not a refactor.
- **Per-user Anthropic key**: `UserProfile.anthropic_api_key` plus an
  `ANTHROPIC_API_KEY` env/settings fallback. Keys resolve per the chosen model's
  provider (user profile first, then env). Added the missing profile-edit page so
  keys are configurable in the UI.
- **Result caching**: each `Analysis` stores a content `fingerprint`
  (prompt-version + provider + model + advisory/patch). Re-requesting an
  unchanged analysis reuses the stored row instead of re-spending tokens and
  shows a "reused — Regenerate to refresh" notice; **Regenerate** always
  re-runs. Changing the advisory, model, provider, or prompt version
  invalidates automatically.
- Pinned `anthropic==0.69.0` (verified compatible with the existing
  `httpx==0.27.2` pin).

#### Changed
- `AnalysisService` resolves a provider from the model instead of talking to
  OpenAI directly; cost comes from the catalog pricing table (Claude pricing is
  a marked maintainer TODO — unpriced models estimate `0.0`, never a fabricated
  number). In-provider model fallback never crosses providers/keys.

### Sprint 1 — Trustworthy analysis + readable diffs

#### Security
- HTML-escape all diff content in template filters, closing a stored-XSS hole
  where patch text could inject markup.
- Remove the OpenAI client's subprocess/eval fallback that wrote the API key to
  a temp file and executed generated code.

#### Analysis
- Move analysis onto the modern OpenAI SDK (1.x) with JSON-object output and
  replace brittle markdown regex-scraping with `json.loads`; scores are clamped
  to 0–10 and malformed responses fail gracefully.
- Add `severity`, `cwe`, `confidence`, `tokens_used`, and `estimated_cost` to
  the `Analysis` model; surface them (plus model and a Regenerate action) on the
  analysis detail page.

#### Diff UX
- New GitHub-style unified diff viewer: line-number gutter, Pygments syntax
  highlighting, add/remove tinting, a +/- change marker (so changes read
  without relying on color), per-file accordion on the commit page, and a
  binary-file state. Retires the ad-hoc raw/enhanced/word-diff rendering and
  the unused `diff-match-patch`-based template filters (and the dependency).

#### Fixes
- Regenerating an analysis now replaces the previous one instead of leaving a
  stale duplicate row for the advisory.
- Cost estimation uses a single pricing table (the OpenAI client's), fed the
  prompt/completion token split.
- Corrected a mislabeled section in the generated markdown report.

### Changed
- **Renamed the project to POCanator.** The Django settings package
  `plurium_pocanator/` is now `pocanator/`, and all module references
  (`DJANGO_SETTINGS_MODULE`, WSGI/ASGI, Docker image/container names, templates)
  were updated accordingly. Remaining legacy "ReportGPT" branding was also
  normalized to POCanator.
- The standalone CLI `reportgpt.py` is now `pocanator.py`.

### Added
- Open-source project scaffolding: `LICENSE` (Apache-2.0), `NOTICE`,
  `SECURITY.md` (responsible-use policy and vulnerability reporting),
  `CONTRIBUTING.md`, and `CODE_OF_CONDUCT.md`.
- Rewritten `README.md` with setup, configuration, and responsible-use guidance.

### Removed
- Dead duplicate Django package `reportgpt_web/` (superseded by `pocanator/`).
- One-off development scripts and artifacts (`fix_*.sh`, `fix_*.py`,
  `phase4_update.sh`, `RENAMING.md`, the oversized `CHANGES.md` dev log,
  duplicate standalone script, orphaned `patch_analysis.py` and its template,
  and sample GHSA analysis outputs).

## [1.0.0] - 2025-03-26

### Added
- Enhanced PoC generation with advanced prompt engineering techniques
  - Multi-stage prompting for structured vulnerability analysis
  - Example-guided generation with concrete code examples for different vulnerability types
  - Framework-specific security guidance for popular frameworks
- Educational focus for security content
  - Side-by-side examples of vulnerable and secure code patterns
  - Clear security best practices
  - Detailed explanations of security concepts
- Fixed advisory title extraction from GitHub
  - Implemented robust title extraction with multiple fallback mechanisms
  - Created Django management command to update existing advisories
- Fixed progress bar display during analysis creation
  - Added proper null checks in JavaScript
  - Improved loading indicator behavior
