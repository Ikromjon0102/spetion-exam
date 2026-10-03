"""DOCX question extraction via python-docx. Splits paragraphs into question
blocks (PARSER_QUESTION_PATTERNS), extracts options per block
(PARSER_OPTION_PATTERNS), and detects the correct option via, in order:
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

from app.parsers.base import BaseParser, ParsedOption, ParsedQuestion
from app.parsers.text_split import (
    extract_answer_key,
    is_option_start,
    is_question_start,
    question_number,
    split_block,
    split_into_blocks,
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


class DocxParser(BaseParser):
    def parse(self, file_bytes: bytes) -> list[ParsedQuestion]:
        document = Document(io.BytesIO(file_bytes))
        numbering = _AutoNumbering(document)

        lines: list[dict] = []
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            label = numbering.label_for(paragraph)
            if not text:
                continue
            # Only prepend Word's auto-number when the text doesn't already
            # carry a literal marker of its own (a hand-typed "1." inside a
            # list item would otherwise end up doubled).
            if label and not is_question_start(text) and not is_option_start(text):
                text = f"{label} {text}"
            bold = any(run.bold for run in paragraph.runs if run.text.strip())
            lines.append({"text": text, "bold": bool(bold)})

        body_lines, key_lines = split_off_answer_key(lines)
        answer_key = {**_extract_table_answer_key(document), **extract_answer_key(key_lines)}
        blocks = split_into_blocks(body_lines)

        questions: list[ParsedQuestion] = []
        for block in blocks:
            prompt, option_lines = split_block(block)
            if not prompt or not option_lines:
                continue

            num = question_number(block)
            correct_letter = answer_key.get(num) if num is not None else None

            options: list[ParsedOption] = []
            for i, opt in enumerate(option_lines):
                letter = chr(ord("A") + i)
                is_correct = (correct_letter == letter) if correct_letter else opt["bold"]
                options.append(ParsedOption(text=opt["text"], is_correct=is_correct))

            # "high" no longer requires exactly 4 options — publish_exam
            # only requires >=2 now (the fixed-4-option rule was relaxed on
            # the user's explicit request), so a clean 3- or 5-option parse
            # with a matched answer-key letter deserves "high" just as much.
            confidence = "high" if (correct_letter and len(options) >= 2) else "low"
            questions.append(ParsedQuestion(prompt=prompt, options=options, confidence=confidence))

        return questions
