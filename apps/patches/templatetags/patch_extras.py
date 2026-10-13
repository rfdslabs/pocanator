from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
from diff_match_patch import diff_match_patch

register = template.Library()

@register.filter
def format_diff(diff_text):
    """Format raw diff text into pretty HTML using diff_match_patch"""
    if not diff_text:
        return ""

    # Create a simple HTML-friendly version of the diff.
    # Every line is HTML-escaped before it is wrapped so that attacker-controlled
    # patch content can never inject markup (stored XSS).
    lines = diff_text.split('\n')
    html_lines = []

    for line in lines:
        safe = escape(line)
        if line.startswith('+') and not line.startswith('+++'):
            html_lines.append(f'<span class="diff-add-line">{safe}</span>')
        elif line.startswith('-') and not line.startswith('---'):
            html_lines.append(f'<span class="diff-remove-line">{safe}</span>')
        elif line.startswith('@@'):
            html_lines.append(f'<span class="diff-hunk-header">{safe}</span>')
        elif line.startswith('diff ') or line.startswith('index ') or line.startswith('---') or line.startswith('+++'):
            html_lines.append(f'<span class="diff-meta">{safe}</span>')
        else:
            html_lines.append(safe)

    return mark_safe('<br>'.join(html_lines))

@register.filter
def diff_files(old_content, new_content):
    """Generate a pretty HTML diff between two text strings"""
    if old_content is None:
        old_content = ""
    if new_content is None:
        new_content = ""
    
    dmp = diff_match_patch()
    diffs = dmp.diff_main(old_content, new_content)
    dmp.diff_cleanupSemantic(diffs)
    
    return mark_safe(dmp.diff_prettyHtml(diffs))

@register.filter
def diff_lines(old_content, new_content):
    """Generate a line-by-line diff with insertions and deletions highlighted"""
    if old_content is None:
        old_content = ""
    if new_content is None:
        new_content = ""
    
    dmp = diff_match_patch()
    
    # Split by lines to do a line-by-line diff
    old_lines = old_content.splitlines()
    new_lines = new_content.splitlines()
    
    # Compare line by line
    html_output = []
    line_diffs = dmp.diff_linesToChars(old_content, new_content)
    line_text1 = line_diffs[0]
    line_text2 = line_diffs[1]
    line_array = line_diffs[2]
    
    diffs = dmp.diff_main(line_text1, line_text2, False)
    dmp.diff_charsToLines(diffs, line_array)
    
    # Format the output
    for op, data in diffs:
        if op == 0:  # Equal
            for line in data.splitlines():
                html_output.append(f'<div class="diff-line diff-equal">{line}</div>')
        elif op == -1:  # Deletion
            for line in data.splitlines():
                html_output.append(f'<div class="diff-line diff-delete">- {line}</div>')
        elif op == 1:  # Insertion
            for line in data.splitlines():
                html_output.append(f'<div class="diff-line diff-insert">+ {line}</div>')
    
    return mark_safe('\n'.join(html_output))

@register.filter
def highlight_diff(content):
    """Highlight diff syntax in a commit diff text"""
    if not content:
        return ""
    
    # This function formats Git-style diff output with syntax highlighting
    lines = content.split('\n')
    html_lines = []
    
    in_diff_header = False
    in_hunk_header = False

    for line in lines:
        safe = escape(line)
        if line.startswith('diff --git'):
            in_diff_header = True
            html_lines.append(f'<div class="diff-header">{safe}</div>')
        elif in_diff_header and (line.startswith('---') or line.startswith('+++')):
            html_lines.append(f'<div class="diff-file-header">{safe}</div>')
        elif line.startswith('@@'):
            in_diff_header = False
            in_hunk_header = True
            html_lines.append(f'<div class="diff-hunk-header">{safe}</div>')
        elif line.startswith('+') and not line.startswith('+++'):
            in_hunk_header = False
            html_lines.append(f'<div class="diff-add">{safe}</div>')
        elif line.startswith('-') and not line.startswith('---'):
            in_hunk_header = False
            html_lines.append(f'<div class="diff-remove">{safe}</div>')
        else:
            in_hunk_header = False
            html_lines.append(f'<div class="diff-context">{safe}</div>')

    return mark_safe('\n'.join(html_lines))