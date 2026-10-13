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
