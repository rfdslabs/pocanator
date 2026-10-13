# Sprint 1 Implementation Plan — Trustworthy Analysis + Readable Diffs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make POCanator's vulnerability analysis reliable (structured output on a modern SDK) and its diff viewer readable and safe, as one demoable OSS-launch slice.

**Architecture:** Keep the existing Django app structure. The LLM transport (`openai_compat.OpenAIClient`) becomes a thin OpenAI ≥1.x client that can request JSON-schema output; `AnalysisService` maps that JSON onto the `Analysis` model instead of regex-scraping prose; the diff presentation moves into an escaped, Pygments-highlighted inclusion tag + partial driving `FileChange`/`LineChange`.

**Tech Stack:** Python 3.10, Django 4.2, `openai==1.51.0`, `pygments` (installed), `diff-match-patch` (being retired from rendering), Django `TestCase` test runner.

**Spec:** `docs/superpowers/specs/2026-10-12-sprint1-analysis-diff-ux-design.md`

## Global Constraints

- Supported interpreter is **Python 3.10**; use `venv310/bin/python` for all commands. Dependencies must install from wheels on 3.10.
- Run tests with `venv310/bin/python manage.py test <app>` (no pytest; no network in tests — always mock the LLM client).
- Migrations are disabled (`MIGRATION_MODULES=None`); schema is applied via `migrate --run-syncdb`, so **new model fields must be nullable or have defaults** and need no migration file.
- Branding is **POCanator**; do not reintroduce `plurium`/`reportgpt` strings.
- Commit message trailer on every commit: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Never write the API key to disk or execute generated code.

## Review Focus

1. **Patch text containing HTML/JS** (`<script>`, `<img onerror=…>`) in `diff_text`/`LineChange.content` — must render inert, never execute. (Task 1)
2. **LLM returns malformed or non-JSON content** — analysis must fail gracefully (user-visible error, no 500, no half-saved row). (Task 4)
3. **Out-of-range / "N/A" scores** from the model (e.g. `patch_effectiveness: "high"`, `12`) — coerced into 0–10 ints. (Task 4)
4. **No OpenAI key / client unavailable** — create & regenerate show a clear message, not a crash. (Tasks 3, 7)
5. **Binary or empty file changes** in a commit — diff viewer shows a "binary"/"no changes" state, not blank or a traceback. (Task 5)

---

### Task 1: Escape diff content in template filters (security)

**Files:**
- Modify: `apps/patches/templatetags/patch_extras.py`
- Create: `apps/patches/tests.py`

**Interfaces:**
- Produces: `format_diff(text)`, `highlight_diff(text)` — return `SafeString` with all source content HTML-escaped.

- [ ] **Step 1: Write failing tests**

```python
# apps/patches/tests.py
from django.test import TestCase
from apps.patches.templatetags.patch_extras import format_diff, highlight_diff

XSS = "+<script>alert(1)</script>"

class DiffFilterEscapingTests(TestCase):
    def test_format_diff_escapes_content(self):
        out = format_diff(XSS)
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_highlight_diff_escapes_content(self):
        out = highlight_diff("-<img src=x onerror=alert(1)>")
        self.assertNotIn("<img src=x onerror", out)
        self.assertIn("&lt;img", out)

    def test_format_diff_keeps_structural_classes(self):
        out = format_diff("+added line")
        self.assertIn("diff-add-line", out)
```

- [ ] **Step 2: Run, verify failure**

Run: `venv310/bin/python manage.py test apps.patches -v 2`
Expected: FAIL (raw `<script>` present).

- [ ] **Step 3: Implement escaping**

In `patch_extras.py`, `from django.utils.html import escape`. In `format_diff` and `highlight_diff`, escape the line before building each span/div, e.g. `safe = escape(line)` then wrap `safe`. Keep class logic keyed on the original `line.startswith(...)` prefix.

- [ ] **Step 4: Run, verify pass**

Run: `venv310/bin/python manage.py test apps.patches -v 2` → PASS

- [ ] **Step 5: Commit**

```bash
git add apps/patches/templatetags/patch_extras.py apps/patches/tests.py
git commit -m "fix(patches): HTML-escape diff content in template filters (XSS)"
```

---

### Task 2: Remove subprocess/eval fallback from the OpenAI client (security)

**Files:**
- Modify: `apps/analysis/openai_compat.py`
- Create: `apps/analysis/tests.py`

**Interfaces:**
- Produces: `OpenAIClient.chat_completion(...)` raises the underlying exception on failure; no temp file, no `subprocess`.

- [ ] **Step 1: Write failing test**

```python
# apps/analysis/tests.py
from unittest import mock
from django.test import TestCase
from apps.analysis.openai_compat import OpenAIClient

class ClientNoSubprocessTests(TestCase):
    def test_no_subprocess_on_failure(self):
        client = OpenAIClient(api_key="test-key")
        with mock.patch("subprocess.check_output") as sp:
            with mock.patch.object(client, "_create", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    client.chat_completion(model="gpt-4o", messages=[{"role":"user","content":"hi"}])
            sp.assert_not_called()
```

- [ ] **Step 2: Run, verify failure** (`_create` not defined yet / subprocess still called)

Run: `venv310/bin/python manage.py test apps.analysis.tests.ClientNoSubprocessTests -v 2` → FAIL

- [ ] **Step 3: Implement** — rewrite in Task 3 (this test is satisfied by the Task 3 rewrite that drops the subprocess block and routes calls through a `_create` method). Mark Step 4 after Task 3.

- [ ] **Step 4: Run after Task 3** → PASS
- [ ] **Step 5: Committed as part of Task 3.**

---

### Task 3: Modern OpenAI ≥1.x client with structured output

**Files:**
- Modify: `requirements.txt`, `apps/analysis/openai_compat.py`
- Test: `apps/analysis/tests.py`

**Interfaces:**
- Produces: `OpenAIClient.chat_completion(model, messages, temperature=0.2, max_tokens=None, response_format=None)` → `{"content": str, "tokens": {"prompt_tokens","completion_tokens","total_tokens"}, "model": str, "elapsed_time": float}`. Internal `_create(**params)` wraps `self._client.chat.completions.create`.

- [ ] **Step 1: Bump requirement**

In `requirements.txt` replace `openai==0.28.1` with `openai==1.51.0`. Install:
`venv310/bin/python -m pip install -r requirements.txt`

- [ ] **Step 2: Write failing test**

```python
# apps/analysis/tests.py (add)
from unittest import mock
from apps.analysis.openai_compat import OpenAIClient

class ChatCompletionTests(TestCase):
    def _fake_response(self):
        m = mock.Mock()
        m.choices = [mock.Mock(message=mock.Mock(content='{"ok": true}'))]
        m.usage = mock.Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        return m

    def test_returns_standard_shape(self):
        client = OpenAIClient(api_key="k")
        with mock.patch.object(client, "_create", return_value=self._fake_response()):
            out = client.chat_completion(model="gpt-4o", messages=[{"role":"user","content":"x"}])
        self.assertEqual(out["content"], '{"ok": true}')
        self.assertEqual(out["tokens"]["total_tokens"], 15)
        self.assertEqual(out["model"], "gpt-4o")
```

- [ ] **Step 3: Run, verify failure** → FAIL

- [ ] **Step 4: Rewrite `openai_compat.py`**

```python
import logging, time
logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self, api_key=None):
        import os
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("No API key provided. Set OPENAI_API_KEY or pass api_key.")
        from openai import OpenAI
        self._client = OpenAI(api_key=self.api_key)

    def _create(self, **params):
        return self._client.chat.completions.create(**params)

    def chat_completion(self, model, messages, temperature=0.2, max_tokens=None, response_format=None, **kwargs):
        start = time.time()
        params = {"model": model, "messages": messages, "temperature": temperature}
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if response_format is not None:
            params["response_format"] = response_format
        params.update({k: v for k, v in kwargs.items() if k not in params})
        resp = self._create(**params)
        content = resp.choices[0].message.content
        u = resp.usage
        return {
            "content": content,
            "tokens": {"prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens, "total_tokens": u.total_tokens},
            "model": model,
            "elapsed_time": time.time() - start,
        }

    def calculate_cost(self, model, tokens):
        pricing = {"gpt-3.5-turbo": (0.0005, 0.0015), "gpt-4": (0.03, 0.06),
                   "gpt-4-turbo": (0.01, 0.03), "gpt-4o": (0.0025, 0.01)}
        if model in pricing:
            i, o = pricing[model]
            return (tokens["prompt_tokens"]/1_000_000)*i + (tokens["completion_tokens"]/1_000_000)*o
        return (tokens.get("total_tokens", 0)/1_000_000)*0.02
```

- [ ] **Step 5: Run Task 2 + Task 3 tests** → PASS

Run: `venv310/bin/python manage.py test apps.analysis -v 2`

- [ ] **Step 6: Commit**

```bash
git add requirements.txt apps/analysis/openai_compat.py apps/analysis/tests.py
git commit -m "refactor(analysis): modern OpenAI 1.x client, drop subprocess-eval fallback"
```

---

### Task 4: Structured JSON analysis + new Analysis fields

**Files:**
- Modify: `apps/analysis/models.py`, `apps/analysis/services.py`
- Test: `apps/analysis/tests.py`

**Interfaces:**
- Consumes: `OpenAIClient.chat_completion(..., response_format=...)` (Task 3).
- Produces: `Analysis` with new nullable fields `cwe`, `severity`, `confidence`, `tokens_used`, `estimated_cost`; `AnalysisService._parse_analysis_results(content)` returns a dict parsed via `json.loads`; `AnalysisService._build_markdown(data)` renders a report string.

- [ ] **Step 1: Add model fields**

In `apps/analysis/models.py`, add to `Analysis` (all safe for `--run-syncdb`):
```python
severity = models.CharField(max_length=50, blank=True, null=True)
cwe = models.CharField(max_length=50, blank=True, null=True)
confidence = models.IntegerField(default=0, help_text="Model confidence 0-10")
tokens_used = models.IntegerField(default=0)
estimated_cost = models.FloatField(default=0.0)
```
Apply: `venv310/bin/python manage.py migrate --run-syncdb`

- [ ] **Step 2: Write failing test (JSON mapping + coercion)**

```python
# apps/analysis/tests.py (add)
import json
from unittest import mock
from apps.advisories.models import Advisory
from apps.analysis.services import AnalysisService

GOOD = json.dumps({
  "vuln_type":"SQLi","severity":"High","cwe":"CWE-89","confidence":9,
  "vuln_explanation":"e","patch_analysis":"p","impact_summary":"i",
  "patch_effectiveness":9,"poc_feasibility":"N/A","poc_complexity":"Medium",
  "required_skills":"sql","information_gaps":"none","key_indicators":"concat"})

class StructuredAnalysisTests(TestCase):
    def setUp(self):
        self.adv = Advisory.objects.create(github_id="GHSA-x", url="http://x", title="t",
            description="d", severity="High")

    def test_maps_json_to_analysis(self):
        svc = AnalysisService(api_key="k")
        fake = {"content": GOOD, "tokens": {"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}, "model":"gpt-4o","elapsed_time":0.1}
        with mock.patch.object(svc.openai_client, "chat_completion", return_value=fake):
            a = svc.analyze_advisory(self.adv, model="gpt-4o")
        self.assertEqual(a.vuln_type, "SQLi")
        self.assertEqual(a.cwe, "CWE-89")
        self.assertEqual(a.patch_effectiveness, 9)
        self.assertEqual(a.poc_feasibility, 0)   # "N/A" coerced
        self.assertEqual(a.tokens_used, 2)
        self.assertTrue(a.markdown_report)

    def test_malformed_json_returns_none(self):
        svc = AnalysisService(api_key="k")
        fake = {"content":"not json","tokens":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2},"model":"gpt-4o","elapsed_time":0.1}
        with mock.patch.object(svc.openai_client, "chat_completion", return_value=fake):
            self.assertIsNone(svc.analyze_advisory(self.adv, model="gpt-4o"))
```

- [ ] **Step 3: Run, verify failure** → FAIL

- [ ] **Step 4: Implement structured path in `services.py`**

- Request structured output: pass `response_format={"type": "json_object"}` to `chat_completion`, and in the system prompt instruct: "Respond ONLY with a JSON object with keys: vuln_type, severity, cwe, confidence (0-10), vuln_explanation, patch_analysis, impact_summary, patch_effectiveness (0-10), poc_feasibility (0-10), poc_complexity (Low|Medium|High), required_skills, information_gaps, key_indicators."
- Replace `_parse_analysis_results` body with `return json.loads(content)` guarded by `try/except (ValueError, TypeError)` returning `None`; if `None`, `analyze_advisory` logs and returns `None`.
- Map fields onto `Analysis` using `.get(...)` and `_safe_int_conversion` for the three numeric score fields + `confidence`; set `tokens_used`, `estimated_cost = self.openai_client.calculate_cost(model, response["tokens"])`.
- Add `_build_markdown(data)` producing a `##`-sectioned report; store in `markdown_report`.

- [ ] **Step 5: Run, verify pass** → `venv310/bin/python manage.py test apps.analysis -v 2`

- [ ] **Step 6: Commit**

```bash
git add apps/analysis/models.py apps/analysis/services.py apps/analysis/tests.py
git commit -m "feat(analysis): structured JSON analysis with severity/cwe/confidence/cost"
```

---

### Task 5: Diff renderer inclusion tag + partial (pygments, gutter, escaping)

**Files:**
- Create: `apps/patches/templates/patches/_diff.html`
- Modify: `apps/patches/templatetags/patch_extras.py`
- Test: `apps/patches/tests.py`

**Interfaces:**
- Produces: inclusion tag `{% render_file_change file_change %}` → context `{"file_change", "rows", "highlighted": bool, "binary": bool}`; `rows` = list of `{old, new, cls, html}` where `html` is escaped+optionally pygments-highlighted.

- [ ] **Step 1: Write failing test**

```python
# apps/patches/tests.py (add)
from apps.advisories.models import Advisory, Commit
from apps.patches.models import FileChange, LineChange
from apps.patches.templatetags.patch_extras import build_diff_rows

class DiffRowsTests(TestCase):
    def setUp(self):
        adv = Advisory.objects.create(github_id="GHSA-y", url="http://y", title="t", description="d", severity="Low")
        c = Commit.objects.create(advisory=adv, repo_name="o/r", commit_hash="a"*40, commit_url="http://c", diff_text="x")
        self.fc = FileChange.objects.create(commit=c, file_path="app.py", lines_added=1, lines_removed=1)
        LineChange.objects.create(file_change=self.fc, change_type="remove", old_line_num=1, content="bad('<script>')")
        LineChange.objects.create(file_change=self.fc, change_type="add", new_line_num=1, content="safe()")

    def test_rows_escape_and_class(self):
        rows = build_diff_rows(self.fc)
        joined = " ".join(r["html"] for r in rows)
        self.assertNotIn("<script>", joined)
        self.assertEqual(rows[0]["cls"], "diff-remove")
        self.assertEqual(rows[0]["old"], 1)
```

- [ ] **Step 2: Run, verify failure** → FAIL (`build_diff_rows` undefined)

- [ ] **Step 3: Implement `build_diff_rows` + inclusion tag + `_diff.html`**

```python
# patch_extras.py (add)
from django.utils.html import escape
from pygments import highlight
from pygments.lexers import guess_lexer_for_filename
from pygments.lexers.special import TextLexer
from pygments.formatters import HtmlFormatter

_CLS = {"add": "diff-add", "remove": "diff-remove", "context": "diff-context"}

def build_diff_rows(file_change):
    rows = []
    try:
        lexer = guess_lexer_for_filename(file_change.file_path, "")
    except Exception:
        lexer = TextLexer()
    fmt = HtmlFormatter(nowrap=True)
    for lc in file_change.line_changes.all():
        try:
            html = highlight(lc.content, lexer, fmt).strip() or escape(lc.content)
        except Exception:
            html = escape(lc.content)
        rows.append({"old": lc.old_line_num, "new": lc.new_line_num,
                     "cls": _CLS.get(lc.change_type, ""), "html": html})
    return rows

@register.inclusion_tag("patches/_diff.html")
def render_file_change(file_change):
    return {"file_change": file_change, "rows": build_diff_rows(file_change),
            "binary": file_change.is_binary}
```

`_diff.html` renders a `<table class="diff">` with old/new gutter `<td>`s and a content `<td>` printing `{{ row.html|safe }}` (safe because content was escaped before highlighting); shows a "Binary file" row when `binary`.

- [ ] **Step 4: Run, verify pass** → `venv310/bin/python manage.py test apps.patches -v 2`

- [ ] **Step 5: Commit**

```bash
git add apps/patches/templatetags/patch_extras.py apps/patches/templates/patches/_diff.html apps/patches/tests.py
git commit -m "feat(patches): escaped, pygments-highlighted diff rows with line gutter"
```

---

### Task 6: Wire the new diff viewer + file list/collapse into pages

**Files:**
- Modify: `templates/patches/commit_detail.html`, `templates/patches/file_change_detail.html`
- Add: Pygments CSS to `templates/base.html` (or a small `<style>` block) for `.diff-add/.diff-remove/.diff-context` and the `HtmlFormatter` token classes.

**Interfaces:**
- Consumes: `{% render_file_change fc %}` (Task 5); `commit.file_changes.all` for the file list.

- [ ] **Step 1: Commit_detail** — add a per-commit **file summary list** (path, `+{{fc.lines_added}}/-{{fc.lines_removed}}`, binary badge) with a Bootstrap collapse per file wrapping `{% render_file_change fc %}`; `{% load patch_extras %}` at top. Replace old `highlight_diff`/`format_diff` usage.
- [ ] **Step 2: File_change_detail** — replace old diff rendering with `{% render_file_change file_change %}`.
- [ ] **Step 3: Styles** — add CSS: `.diff` table (monospace, full width), green/red row backgrounds for add/remove, muted gutter; include `HtmlFormatter().get_style_defs('.diff')` output once (paste static CSS, not runtime) scoped so it doesn't fight Bootstrap.
- [ ] **Step 4: Manual verify** — start server, open a commit page and a file-change page; confirm gutter, colors, collapse, and that an XSS payload in content is inert (view source shows `&lt;script&gt;`).

Run: `venv310/bin/python manage.py check` then load `/patches/...` pages.

- [ ] **Step 5: Commit**

```bash
git add templates/patches/commit_detail.html templates/patches/file_change_detail.html templates/base.html
git commit -m "feat(patches): GitHub-like diff pages with file list, collapse, highlighting"
```

---

### Task 7: Analysis UX — regenerate, states, cost/tokens

**Files:**
- Modify: `apps/analysis/urls.py`, `apps/analysis/views.py`, `templates/analysis/analysis_detail.html`, `templates/analysis/create_analysis.html`
- Test: `apps/analysis/tests.py`

**Interfaces:**
- Consumes: `AnalysisService.analyze_advisory` (Task 4).
- Produces: URL name `analysis-regenerate` (POST, `pk`) → re-runs analysis for `analysis.advisory`, redirects to detail.

- [ ] **Step 1: Write failing test**

```python
# apps/analysis/tests.py (add)
from django.urls import reverse
from django.contrib.auth.models import User

class RegenerateViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", password="p")
        self.adv = Advisory.objects.create(github_id="GHSA-z", url="http://z", title="t", description="d", severity="Low")
        from apps.analysis.models import Analysis
        self.analysis = Analysis.objects.create(advisory=self.adv, vuln_type="X",
            vuln_explanation="e", patch_analysis="p", impact_summary="i",
            patch_effectiveness=1, poc_feasibility=1, poc_complexity="Low")

    def test_regenerate_requires_login(self):
        r = self.client.post(reverse("analysis-regenerate", args=[self.analysis.pk]))
        self.assertEqual(r.status_code, 302)  # redirected to login
```

- [ ] **Step 2: Run, verify failure** → FAIL (no URL)

- [ ] **Step 3: Implement** — add `RegenerateAnalysisView(LoginRequiredMixin, View)` with `post()` calling the service and redirecting to `analysis-detail`; register `path("<int:pk>/regenerate/", ..., name="analysis-regenerate")`. In `analysis_detail.html` add a **Regenerate** button (POST form with csrf), display `model_used`, `tokens_used`, `estimated_cost`, `confidence`, `severity`, `cwe`. In `create_analysis.html` add a submit spinner + show Django `messages` as alerts (loading/error states).

- [ ] **Step 4: Run, verify pass** → `venv310/bin/python manage.py test apps.analysis -v 2`

- [ ] **Step 5: Commit**

```bash
git add apps/analysis/urls.py apps/analysis/views.py templates/analysis/analysis_detail.html templates/analysis/create_analysis.html apps/analysis/tests.py
git commit -m "feat(analysis): regenerate action, loading/error states, cost+confidence display"
```

---

### Task 8: Full-suite verification + docs

- [ ] **Step 1:** `venv310/bin/python manage.py check` → no issues.
- [ ] **Step 2:** `venv310/bin/python manage.py test` → all pass.
- [ ] **Step 3:** Smoke: restart server, exercise `/advisories/`, a commit diff page, an analysis detail page; confirm no `plurium`/`reportgpt`, XSS inert.
- [ ] **Step 4:** Update `CHANGELOG.md` Unreleased with the sprint items; commit.

## Self-Review

- **Spec coverage:** Item 1 security → Tasks 1–3; Item 2 structured analysis → Tasks 3–4; Item 3 diff UX → Tasks 5–6; Item 4 analysis UX → Task 7. All covered.
- **Placeholder scan:** Task 2's implementation intentionally defers to Task 3 (same file); all other steps carry real code. No TBD/TODO.
- **Type consistency:** `chat_completion` return shape and `{old,new,cls,html}` row dict used consistently across Tasks 3/4/5/6.
- **Review Focus:** (1) XSS → Task 1 + Task 5 tests; (2) malformed JSON → Task 4 `test_malformed_json_returns_none`; (3) score coercion → Task 4 `poc_feasibility "N/A"`→0; (4) no key → Task 3 `__init__` raises / service guards, Task 7 login+message path; (5) binary/empty → Task 5 `binary` flag + `_diff.html` binary row.
