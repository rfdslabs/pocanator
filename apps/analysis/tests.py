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
