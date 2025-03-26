from django import template
import markdown
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def mul(value, arg):
    """Multiply the value by the argument"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def markdown_to_html(text):
    """Convert markdown text to HTML"""
    if not text:
        return ''
    # Configure Markdown with extensions
    md = markdown.Markdown(
        extensions=[
            'markdown.extensions.extra',  # Tables, footnotes, etc.
            'markdown.extensions.codehilite',  # Code highlighting
            'markdown.extensions.fenced_code',  # Fenced code blocks
            'markdown.extensions.toc',  # Table of contents
            'markdown.extensions.smarty'  # Smart quotes
        ]
    )
    # Convert markdown to HTML and mark as safe for Django template
    return mark_safe(md.convert(text))