"""PDF question extraction via pdfplumber, with pytesseract OCR fallback for
scanned pages with no text layer (those questions are flagged low-confidence
— per docs/spec.md section 4 we don't invest in OCR accuracy for v1, just
don't crash). Same question/option engine as docx_parser.py (text_split.py).
A PDF has no reliable bold, so the correct answer comes from a trailing
"Javoblar:" key only — a PDF without one parses with no correct answer
marked and the teacher sets them. Exponents and subscripts are recovered
from character size and baseline (plain extraction flattens "3015^3016" into
"30153016") and stored as rich text.
"""

import io
import re

import pdfplumber
import pytesseract

from app.config import settings
from app.parsers.base import BaseParser, ParsedQuestion
from app.parsers.text_split import (
    SUB,
    SUP,
    extract_answer_key,
    is_option_start,
    is_question_start,
    make_line,
    parse_questions,
    split_off_answer_key,
)

# Some PDF-embedded fonts map spacing/formatting glyphs into the Unicode
# Private Use Area instead of a real space — pdfplumber extracts them
# faithfully, so a real teacher's PDF came through as e.g. "● A 198"
# (bullet, "A", an invisible PUA glyph, space, value). They render as
# nothing/a blank in any normal font, so stripping them is safe and turns
# that back into the plain "A 198" our patterns already expect — don't
# reintroduce per-pattern workarounds for this, strip once at the source.
_PUA_RE = re.compile(r"[\ue000-\uf8ff]")

_PAGE_NUMBER_RE = re.compile(r"^\d{1,3}$")
# a character this much smaller than its line, and raised/lowered this much
# against the line's baseline, is an exponent / subscript
_SMALL = 0.85
_RAISED = 0.2


def _line_from_chars(chars: list[dict]):
    """(text, fmt) for one PDF line, with exponents (a smaller, raised
    character) and subscripts recovered — plain extraction flattens
    "3015^3016" into "30153016"."""
    sizes = [round(c["size"], 1) for c in chars if c["text"].strip()]
    if not sizes:
        return "", []
    base = max(set(sizes), key=sizes.count)
    on_base = [c["bottom"] for c in chars if c["size"] >= base * 0.95 and c["text"].strip()]
    base_bottom = sorted(on_base)[len(on_base) // 2] if on_base else chars[0]["bottom"]

    text: list[str] = []
    fmt: list[int] = []
    prev = None
    for c in chars:
        if prev is not None and c["text"] != " " and c["x0"] - prev["x1"] > 3:
            text.append(" ")
            fmt.append(0)
        bits = 0
        if c["text"].strip() and c["size"] < base * _SMALL:
            raised = base_bottom - c["bottom"]
            if raised > base * _RAISED:
                bits = SUP
            elif -raised > base * _RAISED * 0.75:
                bits = SUB
        text.append(c["text"])
        fmt.append(bits)
        prev = c
    return "".join(text), fmt


class PdfParser(BaseParser):
    def parse(self, file_bytes: bytes) -> list[ParsedQuestion]:
        pages: list[list[dict]] = []

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_lines: list[dict] = []
                text_lines = page.extract_text_lines(return_chars=True) if page.chars else []
                if not text_lines:
                    # scanned page: no text layer at all
                    for raw in self._ocr_page(page).split("\n"):
                        line = make_line(_PUA_RE.sub("", raw), ocr=True)
                        if line:
                            page_lines.append(line)
                else:
                    for tl in text_lines:
                        text, fmt = _line_from_chars(tl["chars"])
                        # PUA glyphs are invisible spacing from odd fonts — strip
                        # them once here (see the note above _PUA_RE's old home
                        # in the git history: don't add per-pattern workarounds)
                        keep = [i for i, ch in enumerate(text) if not _PUA_RE.match(ch)]
                        line = make_line("".join(text[i] for i in keep), [fmt[i] for i in keep])
                        if line and not _PAGE_NUMBER_RE.match(line["text"]):
                            page_lines.append(line)
                pages.append(page_lines)

        # a running header/footer repeats on every page; left in, it would be
        # glued onto the last option of the question above it
        if len(pages) >= 2:
            common = set.intersection(*[{ln["text"] for ln in p} for p in pages])
            common = {t for t in common if not is_question_start(t) and not is_option_start(t)}
            pages = [[ln for ln in p if ln["text"] not in common] for p in pages]

        lines = [ln for p in pages for ln in p]
        body_lines, key_lines = split_off_answer_key(lines)
        return parse_questions(body_lines, extract_answer_key(key_lines))

    def _ocr_page(self, page) -> str:
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        try:
            image = page.to_image(resolution=200).original
            return pytesseract.image_to_string(image)
        except Exception:
            return ""
