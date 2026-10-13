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


class DiffRowsTests(TestCase):
    def setUp(self):
        from apps.advisories.models import Advisory, Commit
        from apps.patches.models import FileChange, LineChange
        adv = Advisory.objects.create(github_id="GHSA-y", url="http://y", title="t",
                                      description="d", severity="Low")
        c = Commit.objects.create(advisory=adv, repo_name="o/r", commit_hash="a" * 40,
                                  commit_url="http://c", diff_text="x")
        self.fc = FileChange.objects.create(commit=c, file_path="app.py",
                                            lines_added=1, lines_removed=1)
        LineChange.objects.create(file_change=self.fc, change_type="remove",
                                  old_line_num=1, content="bad('<script>')")
        LineChange.objects.create(file_change=self.fc, change_type="add",
                                  new_line_num=1, content="safe()")

    def test_rows_escape_and_class(self):
        from apps.patches.templatetags.patch_extras import build_diff_rows
        rows = build_diff_rows(self.fc)
        joined = " ".join(r["html"] for r in rows)
        self.assertNotIn("<script>", joined)
        self.assertEqual(rows[0]["cls"], "diff-remove")
        self.assertEqual(rows[0]["old"], 1)
        self.assertEqual(rows[1]["cls"], "diff-add")
        self.assertEqual(rows[1]["new"], 1)
