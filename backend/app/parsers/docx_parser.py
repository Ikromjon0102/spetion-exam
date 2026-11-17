"""DOCX question extraction via python-docx. Splits paragraphs into question
blocks (PARSER_QUESTION_PATTERNS), extracts options per block
(see text_split.py), and detects the correct option via, in order:
a trailing "Javoblar:" answer key in the paragraph text, an answer-key
*table* (a real format seen in the wild: a "Savol"/"Javob" row pair with
question numbers and letters), or bold-run fallback. Never auto-clears
needs_review here — that decision belongs to the teacher review step (see
docs/spec.md section 4).
"""

import io
import re

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from app.parsers.base import BaseParser, ParsedQuestion
from app.parsers.text_split import (
    BOLD,
    SUB,
    SUP,
    extract_answer_key,
    is_option_start,
    is_question_start,
    make_line,
    parse_questions,
    split_off_answer_key,
)

_ANSWER_ROW_LABELS = {"javob", "javoblar"}
_QUESTION_ROW_LABELS = {"savol", "savollar"}


def _extract_table_answer_key(document: Document) -> dict[int, str]:
    """Some exam files carry the answer key as a table instead of inline
    text: one row of question numbers headed "Savol", immediately followed
    by a row of option letters headed "Javob" (repeated in blocks of N
    columns for a wide exam). python-docx only reads paragraph text by
    default, so tables need this separate pass."""
    key: dict[int, str] = {}
    for table in document.tables:
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        for i in range(len(rows) - 1):
            header, values = rows[i], rows[i + 1]
            if not header or not values:
                continue
            if header[0].strip().lower() not in _QUESTION_ROW_LABELS:
                continue
            if values[0].strip().lower() not in _ANSWER_ROW_LABELS:
                continue
            for num_text, letter in zip(header[1:], values[1:]):
                if num_text.strip().isdigit() and re.match(r"^[A-Da-d]$", letter.strip()):
                    key[int(num_text.strip())] = letter.strip().upper()
    return key


_NUMBERED_FORMATS = {"decimal", "upperLetter", "lowerLetter"}


class _AutoNumbering:
    """Word's automatic list numbering ("1.", "2.", "A.", "B." typed via the
    list buttons, not as literal characters) is NOT part of paragraph.text —
    python-docx just sees the bare question text, so every such question
    silently lost its marker and merged into the previous one. This
    reconstructs the label Word would have displayed: it follows the
    paragraph's own (or its style's) numPr to the numbering definition,
    counts occurrences per list/level, and formats them per numFmt/lvlText.
    Bullets and unsupported formats yield no label (left exactly as before)."""

    def __init__(self, document: Document) -> None:
        self._num_to_abstract: dict[str, str] = {}
        self._levels: dict[str, dict[str, tuple[str, str]]] = {}
        self._counters: dict[tuple[str, int], int] = {}
        try:
            root = document.part.numbering_part.element
        except Exception:
            return
        for num in root.findall(qn("w:num")):
            abstract = num.find(qn("w:abstractNumId"))
            if abstract is not None:
                self._num_to_abstract[num.get(qn("w:numId"))] = abstract.get(qn("w:val"))
        for abstract in root.findall(qn("w:abstractNum")):
            levels: dict[str, tuple[str, str]] = {}
            for lvl in abstract.findall(qn("w:lvl")):
                fmt = lvl.find(qn("w:numFmt"))
                text = lvl.find(qn("w:lvlText"))
                levels[lvl.get(qn("w:ilvl"))] = (
                    fmt.get(qn("w:val")) if fmt is not None else "",
                    text.get(qn("w:val")) if text is not None else "",
                )
            self._levels[abstract.get(qn("w:abstractNumId"))] = levels

    @staticmethod
    def _num_pr(paragraph):
        """(numId, ilvl) from the paragraph itself, else from its style chain."""
        p_pr = paragraph._p.pPr
        if p_pr is not None and p_pr.numPr is not None and p_pr.numPr.numId is not None:
            ilvl = p_pr.numPr.ilvl.val if p_pr.numPr.ilvl is not None else 0
            return str(p_pr.numPr.numId.val), int(ilvl)
        style = paragraph.style
        while style is not None:
            s_pr = style.element.pPr
            if s_pr is not None and s_pr.numPr is not None and s_pr.numPr.numId is not None:
                ilvl = s_pr.numPr.ilvl.val if s_pr.numPr.ilvl is not None else 0
                return str(s_pr.numPr.numId.val), int(ilvl)
            style = style.base_style
        return None

    def label_for(self, paragraph) -> str:
        """The marker Word shows for this paragraph, or "" if it isn't a
        supported numbered paragraph. Counting happens for every numbered
        paragraph, in document order, so the sequence stays correct."""
        found = self._num_pr(paragraph)
        if found is None or found[0] == "0":
            return ""
        num_id, ilvl = found
        count = self._counters.get((num_id, ilvl), 0) + 1
        self._counters[(num_id, ilvl)] = count
        # a new item at a shallower level restarts every deeper level
        for key in [k for k in self._counters if k[0] == num_id and k[1] > ilvl]:
            del self._counters[key]

        fmt, template = self._levels.get(self._num_to_abstract.get(num_id, ""), {}).get(str(ilvl), ("", ""))
        if fmt not in _NUMBERED_FORMATS or not template:
            return ""
        if fmt == "decimal":
            value = str(count)
        elif fmt == "upperLetter":
            value = chr(ord("A") + (count - 1) % 26)
        else:
            value = chr(ord("a") + (count - 1) % 26)
        return template.replace(f"%{ilvl + 1}", value)


def _paragraph_line(paragraph, numbering: "_AutoNumbering") -> dict | None:
    """One paragraph as a line with per-character formatting (bold / sub /
    superscript), so an inline row like "A)4 ta  B)6 ta" with ONE bold run
    still tells which option is marked correct."""
    label = numbering.label_for(paragraph)
    text_parts: list[str] = []
    fmt: list[int] = []
    flags: set[str] = set()

    def add(text: str, bits: int) -> None:
        text_parts.append(text)
        fmt.extend([bits] * len(text))

    for child in paragraph._p.iterchildren():
        tag = child.tag
        runs = []
        if tag == qn("w:r"):
            runs = [Run(child, paragraph)]
        elif tag == qn("w:hyperlink"):
            runs = [Run(r, paragraph) for r in child.findall(qn("w:r"))]
        elif tag in (qn("m:oMath"), qn("m:oMathPara")):
            # A Word equation isn't in paragraph.text at all. Keep its text so
            # the question doesn't silently lose it, and mark the question as
            # needing a look — the layout (fractions, roots) is not rebuilt.
            add("".join(t.text or "" for t in child.iter(qn("m:t"))), 0)
            flags.add("formula")
        for run in runs:
            if run._r.findall(qn("w:drawing")) or run._r.findall(qn("w:pict")):
                flags.add("image")
            bits = 0
            if run.bold:
                bits |= BOLD
            if run.font.subscript:
                bits |= SUB
            if run.font.superscript:
                bits |= SUP
            add(run.text, bits)

    text = "".join(text_parts)
    if not text.strip():
        return None
    # Only prepend Word's auto-number when the text doesn't already carry a
    # literal marker of its own (a hand-typed "1." inside a list item would
    # otherwise end up doubled).
    if label and not is_question_start(text.strip()) and not is_option_start(text.strip()):
        fmt = [0] * (len(label) + 1) + fmt
        text = f"{label} {text}"
    return make_line(text, fmt, flags=flags)


def _is_answer_key_table(table) -> bool:
    for row in table.rows:
        first = row.cells[0].text.strip().lower() if row.cells else ""
        if first in _QUESTION_ROW_LABELS | _ANSWER_ROW_LABELS:
            return True
    return False


def _document_lines(document: Document, numbering: "_AutoNumbering") -> list[dict]:
    """Every paragraph in document order, INCLUDING paragraphs inside tables
    (a test laid out as a table used to parse as 0 questions). An answer-key
    table is skipped here — _extract_table_answer_key reads it."""
    lines: list[dict] = []
    body = document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            line = _paragraph_line(Paragraph(child, document), numbering)
            if line:
                lines.append(line)
        elif child.tag == qn("w:tbl"):
            table = Table(child, document)
            if _is_answer_key_table(table):
                continue
            seen: set[int] = set()
            for row in table.rows:
                for cell in row.cells:
                    if id(cell._tc) in seen:  # a merged cell repeats itself
                        continue
                    seen.add(id(cell._tc))
                    for p in cell.paragraphs:
                        line = _paragraph_line(p, numbering)
                        if line:
                            lines.append(line)
    return lines


class DocxParser(BaseParser):
    def parse(self, file_bytes: bytes) -> list[ParsedQuestion]:
        document = Document(io.BytesIO(file_bytes))
        numbering = _AutoNumbering(document)

        lines = _document_lines(document, numbering)
        body_lines, key_lines = split_off_answer_key(lines)
        answer_key = {**_extract_table_answer_key(document), **extract_answer_key(key_lines)}
        return parse_questions(body_lines, answer_key)
