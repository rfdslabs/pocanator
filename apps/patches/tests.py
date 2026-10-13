from django.test import TestCase


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

    def test_rows_have_change_markers(self):
        # Add/remove must be distinguishable by a +/- marker, not color alone.
        from apps.patches.templatetags.patch_extras import build_diff_rows
        rows = build_diff_rows(self.fc)
        self.assertEqual(rows[0]["marker"], "-")
        self.assertEqual(rows[1]["marker"], "+")


class DeadFiltersRemovedTests(TestCase):
    def test_legacy_diff_filters_are_gone(self):
        # The unused diff_match_patch-based filters (latent XSS surface) were removed.
        from apps.patches.templatetags import patch_extras
        for name in ("format_diff", "highlight_diff", "diff_files", "diff_lines"):
            self.assertFalse(hasattr(patch_extras, name),
                             f"{name} should have been removed")
