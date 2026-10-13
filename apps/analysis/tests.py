import json
import os
from unittest import mock

from django.test import TestCase

from apps.analysis.openai_compat import OpenAIClient


# --- Shared fixtures -------------------------------------------------------

GOOD = json.dumps({
    "vuln_type": "SQLi", "severity": "High", "cwe": "CWE-89", "confidence": 9,
    "vuln_explanation": "e", "patch_analysis": "p", "impact_summary": "i",
    "patch_effectiveness": 9, "poc_feasibility": "N/A", "poc_complexity": "Medium",
    "required_skills": "sql", "information_gaps": "none", "key_indicators": "concat",
})


def _resp(content, model="gpt-4o", tokens=None):
    return {"content": content,
            "tokens": tokens or {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "model": model, "elapsed_time": 0.1}


class FakeProvider:
    """A stand-in LLMProvider for service tests."""
    def __init__(self, responses, cost=0.0):
        self._responses = list(responses)
        self.cost = cost
        self.calls = []

    def chat_completion(self, model, messages, **kwargs):
        self.calls.append(model)
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def calculate_cost(self, model, tokens):
        return self.cost


def _advisory(gid="GHSA-x", sev="High"):
    from apps.advisories.models import Advisory
    return Advisory.objects.create(github_id=gid, url="http://x", title="t",
                                   description="d", severity=sev)


# --- openai_compat (unchanged Sprint 1 behavior) --------------------------

class ClientNoSubprocessTests(TestCase):
    def test_no_subprocess_on_failure(self):
        client = OpenAIClient(api_key="test-key")
        with mock.patch("subprocess.check_output") as sp:
            with mock.patch.object(client, "_create", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    client.chat_completion(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": "hi"}],
                    )
            sp.assert_not_called()


class ChatCompletionTests(TestCase):
    def _fake_response(self):
        m = mock.Mock()
        m.choices = [mock.Mock(message=mock.Mock(content='{"ok": true}'))]
        m.usage = mock.Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        return m

    def test_returns_standard_shape(self):
        client = OpenAIClient(api_key="k")
        with mock.patch.object(client, "_create", return_value=self._fake_response()):
            out = client.chat_completion(
                model="gpt-4o", messages=[{"role": "user", "content": "x"}]
            )
        self.assertEqual(out["content"], '{"ok": true}')
        self.assertEqual(out["tokens"]["total_tokens"], 15)
        self.assertEqual(out["model"], "gpt-4o")


class ResponseFormatFallbackTests(TestCase):
    def _fake_response(self):
        m = mock.Mock()
        m.choices = [mock.Mock(message=mock.Mock(content='{"ok": true}'))]
        m.usage = mock.Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        return m

    def test_retries_without_response_format_when_unsupported(self):
        client = OpenAIClient(api_key="k")
        err = Exception("response_format of type 'json_object' is not supported with this model")
        with mock.patch.object(client, "_create",
                               side_effect=[err, self._fake_response()]) as create:
            out = client.chat_completion(
                model="gpt-4",
                messages=[{"role": "user", "content": "return json"}],
                response_format={"type": "json_object"},
            )
        self.assertEqual(out["content"], '{"ok": true}')
        self.assertEqual(create.call_count, 2)
        self.assertNotIn("response_format", create.call_args_list[1].kwargs)


# --- Provider registry + catalog ------------------------------------------

class ProviderRegistryTests(TestCase):
    def test_resolve_known_and_unknown(self):
        from apps.analysis.providers import resolve_provider_for_model, UnknownModel
        self.assertEqual(resolve_provider_for_model("gpt-4o"), "openai")
        self.assertEqual(resolve_provider_for_model("claude-sonnet-5-5"), "anthropic")
        with self.assertRaises(UnknownModel):
            resolve_provider_for_model("no-such-model")

    def test_get_provider_classes(self):
        from apps.analysis.providers import get_provider
        from apps.analysis.providers.openai_provider import OpenAIProvider
        from apps.analysis.providers.anthropic_provider import AnthropicProvider
        self.assertIsInstance(get_provider("gpt-4o", api_key="k"), OpenAIProvider)
        self.assertIsInstance(get_provider("claude-sonnet-5-5", api_key="k"), AnthropicProvider)

    def test_grouped_choices_have_both_providers(self):
        from apps.analysis.providers import grouped_choices
        groups = dict(grouped_choices())
        self.assertIn("Claude (Anthropic)", groups)
        self.assertIn("OpenAI", groups)


class AnthropicProviderTests(TestCase):
    def test_maps_claude_response_and_lifts_system(self):
        from apps.analysis.providers.anthropic_provider import AnthropicProvider
        p = AnthropicProvider(api_key="k")
        block = mock.Mock(type="text", text='{"ok":true}')
        resp = mock.Mock(content=[block], usage=mock.Mock(input_tokens=11, output_tokens=7))
        captured = {}

        def fake_create(**params):
            captured.update(params)
            return resp

        with mock.patch.object(p, "_create", side_effect=fake_create):
            out = p.chat_completion(
                model="claude-sonnet-5-5",
                messages=[{"role": "system", "content": "SYS"},
                          {"role": "user", "content": "U"}],
                response_format={"type": "json_object"},
            )
        self.assertEqual(out["content"], '{"ok":true}')
        self.assertEqual(out["tokens"],
                         {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18})
        self.assertEqual(captured["system"], "SYS")          # system lifted out
        self.assertTrue(all(m["role"] != "system" for m in captured["messages"]))
        self.assertNotIn("response_format", captured)        # ignored for Claude

    def test_unpriced_model_costs_zero_not_fabricated(self):
        from apps.analysis.providers.anthropic_provider import AnthropicProvider
        p = AnthropicProvider(api_key="k")
        cost = p.calculate_cost("claude-sonnet-5-5",
                                {"prompt_tokens": 1000, "completion_tokens": 1000, "total_tokens": 2000})
        self.assertEqual(cost, 0.0)

    def test_missing_key_raises(self):
        from apps.analysis.providers.anthropic_provider import AnthropicProvider
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with self.assertRaises(ValueError):
                AnthropicProvider(api_key=None)


# --- Service: structured analysis, fingerprint, caching -------------------

class StructuredAnalysisTests(TestCase):
    def setUp(self):
        self.adv = _advisory()

    def _svc(self):
        from apps.analysis.services import AnalysisService
        return AnalysisService(api_key="k")

    def test_maps_json_to_analysis(self):
        svc = self._svc()
        fake = FakeProvider([_resp(GOOD)])
        with mock.patch.object(svc, "_get_provider", return_value=fake):
            a = svc.analyze_advisory(self.adv, model="gpt-4o")
        self.assertIsNotNone(a)
        self.assertEqual(a.vuln_type, "SQLi")
        self.assertEqual(a.cwe, "CWE-89")
        self.assertEqual(a.patch_effectiveness, 9)
        self.assertEqual(a.poc_feasibility, 0)   # "N/A" coerced
        self.assertEqual(a.tokens_used, 2)
        self.assertEqual(a.provider, "openai")
        self.assertTrue(a.fingerprint)
        self.assertFalse(a.was_cached)
        self.assertTrue(a.markdown_report)

    def test_out_of_range_score_clamped(self):
        svc = self._svc()
        payload = json.loads(GOOD)
        payload["patch_effectiveness"] = 12
        fake = FakeProvider([_resp(json.dumps(payload))])
        with mock.patch.object(svc, "_get_provider", return_value=fake):
            a = svc.analyze_advisory(self.adv, model="gpt-4o")
        self.assertEqual(a.patch_effectiveness, 10)

    def test_malformed_json_returns_none(self):
        svc = self._svc()
        fake = FakeProvider([_resp("not json")])
        with mock.patch.object(svc, "_get_provider", return_value=fake):
            self.assertIsNone(svc.analyze_advisory(self.adv, model="gpt-4o"))


class FallbackModelTests(TestCase):
    def setUp(self):
        self.adv = _advisory(gid="GHSA-fb")

    def test_successful_fallback_is_not_discarded(self):
        from apps.analysis.services import AnalysisService
        svc = AnalysisService(api_key="k")
        good = _resp(GOOD, model="gpt-4o-mini")
        # gpt-4o errors; the in-provider fallback gpt-4o-mini succeeds.
        fake = FakeProvider([RuntimeError("boom"), good])
        with mock.patch.object(svc, "_get_provider", return_value=fake):
            a = svc.analyze_advisory(self.adv, model="gpt-4o")
        self.assertIsNotNone(a)
        self.assertEqual(a.vuln_type, "SQLi")
        self.assertEqual(a.model_used, "gpt-4o-mini")
        self.assertIn("gpt-4o-mini", a.markdown_report)
        self.assertEqual(a.provider, "openai")


class FingerprintTests(TestCase):
    def test_deterministic_and_sensitive(self):
        from apps.analysis.services import AnalysisService
        f = AnalysisService._fingerprint
        base = f("openai", "gpt-4o", "sys", "prompt")
        self.assertEqual(base, f("openai", "gpt-4o", "sys", "prompt"))
        self.assertNotEqual(base, f("anthropic", "gpt-4o", "sys", "prompt"))
        self.assertNotEqual(base, f("openai", "gpt-4-turbo", "sys", "prompt"))
        self.assertNotEqual(base, f("openai", "gpt-4o", "sys2", "prompt"))
        self.assertNotEqual(base, f("openai", "gpt-4o", "sys", "prompt2"))


class CacheReuseTests(TestCase):
    def setUp(self):
        self.adv = _advisory(gid="GHSA-cache")

    def test_identical_request_reuses_without_calling_provider(self):
        from apps.analysis.services import AnalysisService
        from apps.analysis.models import Analysis
        svc = AnalysisService(api_key="k")
        fake = FakeProvider([_resp(GOOD), _resp(GOOD)])
        with mock.patch.object(svc, "_get_provider", return_value=fake):
            a1 = svc.analyze_advisory(self.adv, model="gpt-4o")
            a2 = svc.analyze_advisory(self.adv, model="gpt-4o")
        self.assertFalse(a1.was_cached)
        self.assertTrue(a2.was_cached)
        self.assertEqual(a1.pk, a2.pk)
        self.assertEqual(len(fake.calls), 1)              # provider called once only
        self.assertEqual(Analysis.objects.filter(advisory=self.adv).count(), 1)

    def test_regenerate_bypasses_cache(self):
        from apps.analysis.services import AnalysisService
        svc = AnalysisService(api_key="k")
        fake = FakeProvider([_resp(GOOD), _resp(GOOD)])
        with mock.patch.object(svc, "_get_provider", return_value=fake):
            svc.analyze_advisory(self.adv, model="gpt-4o")
            svc.analyze_advisory(self.adv, model="gpt-4o", use_cache=False)
        self.assertEqual(len(fake.calls), 2)              # re-ran despite a match

    def test_different_model_is_not_a_false_hit(self):
        from apps.analysis.services import AnalysisService
        svc = AnalysisService(api_key="k")
        fake = FakeProvider([_resp(GOOD), _resp(GOOD, model="gpt-4o-mini")])
        with mock.patch.object(svc, "_get_provider", return_value=fake):
            a1 = svc.analyze_advisory(self.adv, model="gpt-4o")
            a2 = svc.analyze_advisory(self.adv, model="gpt-4o-mini")
        self.assertNotEqual(a1.fingerprint, a2.fingerprint)
        self.assertEqual(len(fake.calls), 2)

    def test_empty_patch_advisory_still_fingerprints(self):
        from apps.analysis.services import AnalysisService
        svc = AnalysisService(api_key="k")
        fake = FakeProvider([_resp(GOOD)])
        with mock.patch.object(svc, "_get_provider", return_value=fake):
            a = svc.analyze_advisory(self.adv, model="gpt-4o")  # advisory has no commits
        self.assertTrue(a.fingerprint)


class MissingKeyTests(TestCase):
    def test_missing_provider_key_returns_none_gracefully(self):
        from apps.analysis.services import AnalysisService
        svc = AnalysisService(api_key=None)
        adv = _advisory(gid="GHSA-nokey")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            a = svc.analyze_advisory(adv, model="claude-sonnet-5-5")
        self.assertIsNone(a)


class CostTableTests(TestCase):
    def setUp(self):
        self.adv = _advisory(gid="GHSA-c")

    def test_estimated_cost_from_catalog_pricing(self):
        from apps.analysis.services import AnalysisService
        from apps.analysis.providers.openai_provider import OpenAIProvider
        svc = AnalysisService(api_key="k")
        provider = OpenAIProvider(api_key="k")
        tokens = {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}
        resp = _resp(GOOD, tokens=tokens)
        with mock.patch.object(provider, "chat_completion", return_value=resp):
            with mock.patch.object(svc, "_get_provider", return_value=provider):
                a = svc.analyze_advisory(self.adv, model="gpt-4o")
        expected = provider.calculate_cost("gpt-4o", tokens)
        self.assertGreater(a.estimated_cost, 0)
        self.assertAlmostEqual(a.estimated_cost, expected, places=10)


class MarkdownReportTests(TestCase):
    def test_key_indicators_is_labeled(self):
        from apps.analysis.services import AnalysisService
        svc = AnalysisService(api_key="k")
        data = json.loads(GOOD)
        data["key_indicators"] = "UNIQUE_INDICATOR_TOKEN"
        md = svc._build_markdown(data)
        self.assertIn("Key indicators", md)
        self.assertIn("UNIQUE_INDICATOR_TOKEN", md)


# --- Views -----------------------------------------------------------------

class KeyResolutionTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from apps.users.models import UserProfile
        self.user = User.objects.create_user("kr", password="p")
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def _fresh_user(self):
        # Reload so the cached reverse one-to-one reflects the saved profile,
        # mirroring a real request that fetches the user anew.
        from django.contrib.auth.models import User
        return User.objects.get(pk=self.user.pk)

    def test_user_key_preferred_then_env(self):
        from apps.analysis.views import resolve_api_key
        self.profile.anthropic_api_key = "user-ak"
        self.profile.openai_api_key = "user-ok"
        self.profile.save()
        with self.settings(ANTHROPIC_API_KEY="env-ak", OPENAI_API_KEY="env-ok"):
            self.assertEqual(resolve_api_key(self._fresh_user(), "claude-sonnet-5-5"), "user-ak")
            self.assertEqual(resolve_api_key(self._fresh_user(), "gpt-4o"), "user-ok")
            # falls back to env when the profile has none
            self.profile.anthropic_api_key = ""
            self.profile.save()
            self.assertEqual(resolve_api_key(self._fresh_user(), "claude-sonnet-5-5"), "env-ak")


class RegenerateViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from apps.analysis.models import Analysis
        self.adv = _advisory(gid="GHSA-z", sev="Low")
        self.analysis = Analysis.objects.create(
            advisory=self.adv, vuln_type="X", vuln_explanation="e", patch_analysis="p",
            impact_summary="i", patch_effectiveness=1, poc_feasibility=1, poc_complexity="Low")

    def test_regenerate_requires_login(self):
        from django.urls import reverse
        r = self.client.post(reverse("analysis-regenerate", args=[self.analysis.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login", r.url)


class RegenerateReplaceTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from apps.analysis.models import Analysis
        self.user = User.objects.create_user("u2", password="p")
        self.adv = _advisory(gid="GHSA-r", sev="Low")
        self.old = Analysis.objects.create(
            advisory=self.adv, vuln_type="Old", vuln_explanation="e", patch_analysis="p",
            impact_summary="i", patch_effectiveness=1, poc_feasibility=1, poc_complexity="Low")

    def test_regenerate_replaces_old_row(self):
        from django.urls import reverse
        from apps.analysis.models import Analysis
        self.client.force_login(self.user)

        def fake_analyze(advisory, model=None, **kwargs):
            return Analysis.objects.create(
                advisory=advisory, vuln_type="New", vuln_explanation="e2",
                patch_analysis="p", impact_summary="i", patch_effectiveness=2,
                poc_feasibility=2, poc_complexity="Low")

        with mock.patch("apps.analysis.views.AnalysisService") as Svc:
            Svc.return_value.analyze_advisory.side_effect = fake_analyze
            r = self.client.post(reverse("analysis-regenerate", args=[self.old.pk]))

        self.assertEqual(r.status_code, 302)
        self.assertEqual(Analysis.objects.filter(advisory=self.adv).count(), 1)
        self.assertFalse(Analysis.objects.filter(pk=self.old.pk).exists())
        self.assertEqual(Analysis.objects.get(advisory=self.adv).vuln_type, "New")


class CreateFormTests(TestCase):
    def test_defaults_to_claude_sonnet_and_lists_both_providers(self):
        from apps.analysis.forms import CreateAnalysisForm
        f = CreateAnalysisForm()
        self.assertEqual(f.fields["model"].initial, "claude-sonnet-5-5")
        group_labels = [grp for grp, _ in f.fields["model"].choices]
        self.assertTrue(any("Claude" in g for g in group_labels))
        self.assertTrue(any("OpenAI" in g for g in group_labels))


# --- Requirements lint (Sprint 1) -----------------------------------------

class RequirementsFileTests(TestCase):
    def test_each_requirement_line_parses(self):
        from django.conf import settings
        from packaging.requirements import Requirement, InvalidRequirement
        path = os.path.join(settings.BASE_DIR, "requirements.txt")
        with open(path) as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    Requirement(line)
                except InvalidRequirement as exc:
                    self.fail(f"malformed requirement line {line!r}: {exc}")

    def test_anthropic_is_pinned(self):
        from django.conf import settings
        path = os.path.join(settings.BASE_DIR, "requirements.txt")
        text = open(path).read()
        self.assertIn("anthropic==", text)
