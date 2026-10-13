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
