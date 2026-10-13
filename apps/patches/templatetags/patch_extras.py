from django import template
from django.utils.html import escape

from pygments import highlight as _pyg_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import guess_lexer_for_filename
from pygments.lexers.special import TextLexer
from pygments.util import ClassNotFound

register = template.Library()

# --- Structured diff rendering (line gutter + syntax highlighting) ---------

_CHANGE_CLS = {"add": "diff-add", "remove": "diff-remove", "context": "diff-context"}
_CHANGE_MARKER = {"add": "+", "remove": "-", "context": " "}
_PYG_FORMATTER = HtmlFormatter(nowrap=True)


def _lexer_for(path):
    try:
        return guess_lexer_for_filename(path, "")
    except ClassNotFound:
        return TextLexer()


def build_diff_rows(file_change):
    """Return a list of display rows for a FileChange.

    Each row is ``{"old", "new", "cls", "marker", "html"}`` where ``html`` is
    the line content HTML-escaped and (where possible) syntax-highlighted.
    Content is always escaped before highlighting, so a row's ``html`` is safe
    to mark ``|safe`` in the template. ``marker`` carries the +/-/space glyph so
    additions and removals are distinguishable without relying on color alone.
    """
    lexer = _lexer_for(file_change.file_path)
    rows = []
    # Preserve the order the lines were parsed in (true diff order).
    for lc in file_change.line_changes.order_by("id"):
        try:
            rendered = _pyg_highlight(lc.content, lexer, _PYG_FORMATTER).strip()
        except Exception:
            rendered = ""
        if not rendered:
            rendered = escape(lc.content)
        rows.append({
            "old": lc.old_line_num,
            "new": lc.new_line_num,
            "cls": _CHANGE_CLS.get(lc.change_type, ""),
            "marker": _CHANGE_MARKER.get(lc.change_type, " "),
            "html": rendered,
        })
    return rows


@register.inclusion_tag("patches/_diff.html")
def render_file_change(file_change):
    """Render a single FileChange as a GitHub-style unified diff table."""
    return {
        "file_change": file_change,
        "rows": build_diff_rows(file_change) if not file_change.is_binary else [],
        "binary": file_change.is_binary,
    }
