import json
from unittest import mock

from django.test import TestCase

from apps.analysis.openai_compat import OpenAIClient


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


GOOD = json.dumps({
    "vuln_type": "SQLi", "severity": "High", "cwe": "CWE-89", "confidence": 9,
    "vuln_explanation": "e", "patch_analysis": "p", "impact_summary": "i",
    "patch_effectiveness": 9, "poc_feasibility": "N/A", "poc_complexity": "Medium",
    "required_skills": "sql", "information_gaps": "none", "key_indicators": "concat",
})


class StructuredAnalysisTests(TestCase):
    def setUp(self):
        from apps.advisories.models import Advisory
        self.adv = Advisory.objects.create(
            github_id="GHSA-x", url="http://x", title="t", description="d", severity="High"
        )

    def _svc(self):
        from apps.analysis.services import AnalysisService
        return AnalysisService(api_key="k")

    def _resp(self, content):
        return {"content": content,
                "tokens": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                "model": "gpt-4o", "elapsed_time": 0.1}

    def test_maps_json_to_analysis(self):
        svc = self._svc()
        with mock.patch.object(svc.openai_client, "chat_completion", return_value=self._resp(GOOD)):
            a = svc.analyze_advisory(self.adv, model="gpt-4o")
        self.assertIsNotNone(a)
        self.assertEqual(a.vuln_type, "SQLi")
        self.assertEqual(a.cwe, "CWE-89")
        self.assertEqual(a.patch_effectiveness, 9)
        self.assertEqual(a.poc_feasibility, 0)   # "N/A" coerced
        self.assertEqual(a.tokens_used, 2)
        self.assertTrue(a.markdown_report)

    def test_out_of_range_score_clamped(self):
        svc = self._svc()
        payload = json.loads(GOOD)
        payload["patch_effectiveness"] = 12
        with mock.patch.object(svc.openai_client, "chat_completion", return_value=self._resp(json.dumps(payload))):
            a = svc.analyze_advisory(self.adv, model="gpt-4o")
        self.assertEqual(a.patch_effectiveness, 10)

    def test_malformed_json_returns_none(self):
        svc = self._svc()
        with mock.patch.object(svc.openai_client, "chat_completion", return_value=self._resp("not json")):
            self.assertIsNone(svc.analyze_advisory(self.adv, model="gpt-4o"))


class RegenerateViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from apps.advisories.models import Advisory
        from apps.analysis.models import Analysis
        self.user = User.objects.create_user("u", password="p")
        self.adv = Advisory.objects.create(github_id="GHSA-z", url="http://z", title="t",
                                            description="d", severity="Low")
        self.analysis = Analysis.objects.create(
            advisory=self.adv, vuln_type="X", vuln_explanation="e", patch_analysis="p",
            impact_summary="i", patch_effectiveness=1, poc_feasibility=1, poc_complexity="Low")

    def test_regenerate_requires_login(self):
        from django.urls import reverse
        r = self.client.post(reverse("analysis-regenerate", args=[self.analysis.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login", r.url)


class RequirementsFileTests(TestCase):
    def test_each_requirement_line_parses(self):
        import os
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


class FallbackModelTests(TestCase):
    def setUp(self):
        from apps.advisories.models import Advisory
        self.adv = Advisory.objects.create(github_id="GHSA-fb", url="http://f", title="t",
                                           description="d", severity="High")

    def test_successful_fallback_is_not_discarded(self):
        from apps.analysis.services import AnalysisService
        svc = AnalysisService(api_key="k")
        good = {"content": GOOD,
                "tokens": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                "model": "gpt-4-turbo", "elapsed_time": 0.1}
        # First model (gpt-4o) errors; fallback (gpt-4-turbo) succeeds.
        with mock.patch.object(svc.openai_client, "chat_completion",
                               side_effect=[RuntimeError("boom"), good]):
            a = svc.analyze_advisory(self.adv, model="gpt-4o")
        self.assertIsNotNone(a)            # fallback result must be saved, not discarded
        self.assertEqual(a.vuln_type, "SQLi")
        self.assertEqual(a.model_used, "gpt-4-turbo")
        self.assertIn("gpt-4-turbo", a.markdown_report)  # fallback noted on the report


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
        # The retry must not carry response_format.
        self.assertNotIn("response_format", create.call_args_list[1].kwargs)
