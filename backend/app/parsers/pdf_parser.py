"""PDF question extraction via pdfplumber, with pytesseract OCR fallback for
scanned pages with no text layer (flagged confidence="low" unconditionally —
per docs/spec.md section 4 we don't invest in OCR accuracy for v1, just
don't crash). Same block/option splitting as docx_parser.py. PDF bold-run
detection is unreliable, so the trailing "Javoblar:" answer key is the only
correct-answer signal used here.
"""

import io

import pdfplumber
import pytesseract

from app.parsers.base import BaseParser, ParsedOption, ParsedQuestion
from app.parsers.text_split import (
    extract_answer_key,
    question_number,
    split_block,
    split_into_blocks,
    split_off_answer_key,
)


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
                    stripped = raw_line.strip()
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
            confidence = "high" if (correct_letter and len(option_lines) == 4 and not ocr_used) else "low"
            questions.append(ParsedQuestion(prompt=prompt, options=options, confidence=confidence))

        return questions

    def _ocr_page(self, page) -> str:
        try:
            image = page.to_image(resolution=200).original
            return pytesseract.image_to_string(image)
        except Exception:
            return ""
