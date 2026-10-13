# Sprint 1 Design — Trustworthy Analysis + Readable Diffs

**Date:** 2026-10-12
**Branch:** `sprint1-analysis-diff-ux`
**Status:** Approved (conversational) — spec for review

## Goal / Intent

POCanator is being prepared as an open-source project. This sprint delivers one
coherent, demoable slice that advances all four stated goals — **OSS launch
polish, analysis quality, diff/review UX, and (lightly) scale** — by making the
two things a visitor judges first both *trustworthy* and *readable*:

1. The AI **analysis** of a vulnerability/patch.
2. The **diff viewer** used to read the fixing commits.

Success criteria:

- Analysis fields/scores are populated reliably (not scraped from prose).
- Diffs render like a modern code host (line numbers, highlighting, per-file
  structure) and are safe against stored XSS.
- No secrets written to disk; no code-eval fallback paths.
- Everything works with `DEBUG=True` locally and degrades gracefully with no
  OpenAI key configured.

Non-goals this sprint (see Backlog): background job queue, response caching,
CWE→CVE enrichment, multi-provider LLM support, production/deploy hardening.

## Current State (as read 2026-10-12)

- **Analysis** (`apps/analysis`): `AnalysisService.analyze_advisory()` builds a
  text prompt, calls `openai_compat.OpenAIClient.chat_completion()`, then
  `_parse_analysis_results()` **scrapes** `SEVERITY`, `VULN_TYPE`,
  `PATCH_EFFECTIVENESS`, section bodies, etc. out of free-form markdown with
  layered regex + fallbacks. Fragile and silently lossy.
- **`openai_compat.py`**: supports openai 0.x and 1.x. On failure it writes a
  temp `.py` file **with the API key and messages interpolated in** and runs it
  via `subprocess` — a key-on-disk + code-injection smell. `requirements.txt`
  pins `openai==0.28.1`.
- **Diff UX** (`apps/patches`): diffs parsed into `FileChange`/`LineChange`
  rows; rendered by `templatetags/patch_extras.py` filters that build HTML by
  string concatenation and `mark_safe` **without escaping line content** →
  stored XSS from attacker-controlled patch text. No line numbers, no syntax
  highlighting (though `pygments` is installed), no per-file collapse.

## Approach Decision

**Chosen: A — modernize the analysis engine to the OpenAI SDK ≥ 1.x with
structured (JSON-schema) output.** The compat shim already supports the 1.x
call shape, so the risk is low, and structured output removes the entire
regex-scraping layer. Rejected: (B) stay on 0.28.1 and improve regex — keeps an
EOL SDK and brittle parsing; (C) provider-agnostic abstraction — valuable for
OSS but larger than one sprint → backlog.

## Scope — Four Work Items

### 1. Security hardening (fast, high-credibility)
- **Escape diff content** in every `patch_extras` filter: HTML-escape each line
  before wrapping/`mark_safe`, so patch text can never inject markup. Add
  regression tests feeding `<script>`/`<img onerror>` payloads through the
  filters and asserting they are neutralized.
- **Remove the subprocess-eval fallback** from `openai_compat.py`. Replace with
  a normal exception that the service already handles (it has ret/fallback
  logic). No API key ever touches disk.

### 2. Structured JSON analysis (analysis quality)
- Bump `requirements.txt` to a modern `openai` (1.x) pin.
- Rework `openai_compat.OpenAIClient` into a thin 1.x client exposing
  `chat_completion(..., response_format=...)` and returning `{content, tokens,
  model, elapsed_time}` (unchanged contract for callers). Keep the graceful
  "no client / no key" path.
- Define an **analysis JSON schema** (vuln_type, severity, cwe, vuln_explanation,
  patch_analysis, impact_summary, patch_effectiveness 0–10, poc_feasibility 0–10,
  poc_complexity, required_skills, information_gaps, key_indicators,
  confidence 0–10). Request it via structured output.
- Replace `_parse_analysis_results()` with a `json.loads` + schema-validate +
  coerce step (keep `_safe_int_conversion` as defensive coercion). Keep a
  readable markdown report rendered **from** the structured data for display.
- **Model additions** to `Analysis`: `severity`, `cwe`, `confidence`,
  `tokens_used`, `estimated_cost`. (Migrations are disabled via
  `MIGRATION_MODULES=None`; schema is applied through `migrate --run-syncdb`, so
  new fields need no migration file — they must be nullable/defaulted.)

### 3. GitHub-like diff viewer (diff/review UX)
- New template partial `patches/_diff.html` rendering unified diff per file:
  two-column line-number gutter, add/remove/context styling, hunk headers.
- **Syntax highlighting** via `pygments` (already a dependency), guessing lexer
  from file extension, applied to escaped content.
- **Per-file structure**: a file list / summary (path, +adds/−removes, binary
  badge) with collapse/expand per file.
- Rewrite `patch_extras` to expose one clean filter/inclusion-tag that drives
  the partial from `FileChange`/`LineChange` (deleting the redundant
  `format_diff`/`diff_files`/`diff_lines`/`highlight_diff` sprawl). Optional
  side-by-side toggle is a stretch goal; unified view is the committed target.
- Wire into `patches/commit_detail.html` and `file_change_detail.html`.

### 4. Analysis UX pass (polish + light scale)
- **Regenerate** action on `analysis_detail` (re-run analysis for the advisory).
- Proper **loading + error states** on create/regenerate.
- Surface **model, tokens, and estimated cost** on the detail page (data now
  stored on `Analysis`).

## Architecture / Data Flow

```
Advisory + Commits ──▶ AnalysisService.analyze_advisory()
                           │  builds prompt (unchanged structure)
                           ▼
                    OpenAIClient.chat_completion(response_format=schema)
                           │  returns {content(JSON), tokens, model, elapsed}
                           ▼
                    json.loads + validate + coerce  ──▶  Analysis row
                           │                                  (+severity,cwe,
                           ▼                                   confidence,tokens,cost)
                    render markdown_report from structured fields
                           ▼
          analysis_detail.html (scores, cost, regenerate)

Commit ──▶ FileChange/LineChange ──▶ patch_extras tag ──▶ _diff.html
                                        (escape → pygments → gutter/collapse)
```

Unit boundaries kept small: the LLM client (transport), the service
(orchestration + schema mapping), the diff renderer (presentation). Each is
independently testable.

## Testing Strategy

- **TDD** throughout. Unit tests, no live API calls — mock `OpenAIClient`.
- Security: filter-escaping tests with XSS payloads; assert no `subprocess`/temp
  file path remains in `openai_compat`.
- Analysis: given a canned structured JSON response, assert correct `Analysis`
  field mapping incl. coercion of `"N/A"`/out-of-range scores; assert graceful
  behavior when no key/client.
- Diff: given `FileChange`/`LineChange` fixtures, assert line numbers, add/remove
  classes, escaped content, and highlighted output; binary-file handling.
- Run `python manage.py check` and the full test suite; manual smoke of
  `/advisories/`, a commit diff page, and an analysis detail page.

## Risks / Dependencies

- **OpenAI key**: `prod/.env` has a dummy `OPENAI_API_KEY=sk`. All automated
  tests mock the client; true end-to-end analysis needs a real key from the
  owner. This does not block building or merging the sprint.
- **SDK bump**: modern `openai` needs `httpx`/`pydantic`; verify the pinned set
  installs cleanly on Python 3.10 (the project's supported interpreter).
- **Structured-output model support**: use a model that supports JSON response
  format; keep a plain-JSON-prompt fallback if the schema mode is unavailable.

## Backlog (post-sprint roadmap)

Background/Celery batch analysis · response caching · CWE→CVE/NVD enrichment ·
multi-provider LLM interface · auth + production hardening · deploy pipeline ·
side-by-side diff · CLI/web env-var unification (`openaikey` vs `OPENAI_API_KEY`).
