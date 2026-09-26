"""PDF question extraction via pdfplumber, with pytesseract OCR fallback for
scanned pages with no text layer (flagged confidence="low" unconditionally —
per docs/spec.md section 4 we don't invest in OCR accuracy for v1, just
don't crash). Same block/option splitting as docx_parser.py. PDF bold-run
detection is unreliable, so the trailing "Javoblar:" answer key is the only
correct-answer signal used here.
"""

import io
import re

import pdfplumber
import pytesseract

from app.config import settings
from app.parsers.base import BaseParser, ParsedOption, ParsedQuestion
from app.parsers.text_split import (
    extract_answer_key,
    question_number,
    split_block,
    split_into_blocks,
    split_off_answer_key,
)

# Some PDF-embedded fonts map spacing/formatting glyphs into the Unicode
# Private Use Area instead of a real space — pdfplumber extracts them
# faithfully, so a real teacher's PDF came through as e.g. "● A 198"
# (bullet, "A", an invisible PUA glyph, space, value). They render as
# nothing/a blank in any normal font, so stripping them is safe and turns
# that back into the plain "A 198" our patterns already expect — don't
# reintroduce per-pattern workarounds for this, strip once at the source.
_PUA_RE = re.compile(r"[-]")


class PdfParser(BaseParser):
    def parse(self, file_bytes: bytes) -> list[ParsedQuestion]:
        lines: list[dict] = []
        ocr_used = False

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text or not text.strip():
                    text = self._ocr_page(page)
                    ocr_used = True
                for raw_line in (text or "").split("\n"):
                    stripped = _PUA_RE.sub("", raw_line).strip()
                    if stripped:
                        lines.append({"text": stripped, "bold": False})

        body_lines, key_lines = split_off_answer_key(lines)
        answer_key = extract_answer_key(key_lines)
        blocks = split_into_blocks(body_lines)

        questions: list[ParsedQuestion] = []
        for block in blocks:
            prompt, option_lines = split_block(block)
            if not prompt or not option_lines:
                continue

            num = question_number(block)
            correct_letter = answer_key.get(num) if num is not None else None

            options = [
                ParsedOption(text=opt["text"], is_correct=(correct_letter == chr(ord("A") + i)))
                for i, opt in enumerate(option_lines)
            ]
            # "high" no longer requires exactly 4 options — see docx_parser.py's
            # matching comment, publish_exam only requires >=2 now.
            confidence = "high" if (correct_letter and len(option_lines) >= 2 and not ocr_used) else "low"
            questions.append(ParsedQuestion(prompt=prompt, options=options, confidence=confidence))

        return questions

    def _ocr_page(self, page) -> str:
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        try:
            image = page.to_image(resolution=200).original
            return pytesseract.image_to_string(image)
        except Exception:
            return ""
