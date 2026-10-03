"""Rich-text question/option content.

Teachers author questions in a rich editor (bold, sub/superscript, lists,
formulas). The content is stored in the existing text columns as sanitized
HTML, marked by a leading sentinel comment. The marker (rather than a new
flag column on every table and API shape) is what lets every existing place
that carries a question's text — student exam screen, result page, review
page, duplicate, AI grading — keep passing one string around, while old
plain-text questions stay exactly as they were: anything *without* the
marker is plain text and is never interpreted as HTML (a plain question
literally containing "<b>" must keep showing "<b>").

Never trust the client: everything carrying the marker is run through an
allow-list sanitizer on the way in (see the schema validators), and the
frontend sanitizes again before rendering.
"""

import html
import re

import nh3

RICH_PREFIX = "<!--sp-rich-->"
MAX_LENGTH = 20_000

ALLOWED_TAGS = {"p", "br", "strong", "em", "u", "s", "sub", "sup", "ul", "ol", "li", "span", "code"}
ALLOWED_ATTRIBUTES = {"span": {"data-type", "data-latex"}}
_MAX_LATEX = 500

_LATEX_SPAN = re.compile(r'<span[^>]*data-latex="([^"]*)"[^>]*>(?:\s*</span>)?', re.IGNORECASE)


def is_rich(text: str | None) -> bool:
    return bool(text) and text.startswith(RICH_PREFIX)


def _attribute_filter(tag: str, attr: str, value: str) -> str | None:
    if tag == "span" and attr == "data-type":
        return value if value == "inline-math" else None
    if tag == "span" and attr == "data-latex":
        return value if len(value) <= _MAX_LATEX else None
    return value


def sanitize(text: str) -> str:
    """Plain text passes through untouched; rich text is reduced to the
    allow-list. Rich content with nothing visible in it collapses to ""."""
    if len(text) > MAX_LENGTH:
        raise ValueError("Matn juda uzun")
    if not is_rich(text):
        return text
    cleaned = nh3.clean(
        text[len(RICH_PREFIX):],
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        attribute_filter=_attribute_filter,
        strip_comments=True,
        link_rel=None,
    )
    if not cleaned.strip() or (not _visible_text(cleaned) and "data-latex" not in cleaned):
        return ""
    return RICH_PREFIX + cleaned


def _visible_text(cleaned_html: str) -> str:
    return html.unescape(nh3.clean(cleaned_html, tags=set())).strip()


def to_plain_text(text: str | None) -> str:
    """The text a human (or the AI grader) would read: tags dropped, formulas
    kept as their LaTeX source. Plain text is returned unchanged."""
    if not text or not is_rich(text):
        return text or ""
    body = text[len(RICH_PREFIX):]
    body = re.sub(r"</(p|li)>|<br\s*/?>", " ", body, flags=re.IGNORECASE)
    body = _LATEX_SPAN.sub(lambda m: f" {html.unescape(m.group(1))} ", body)
    return re.sub(r"\s+", " ", html.unescape(nh3.clean(body, tags=set()))).strip()
