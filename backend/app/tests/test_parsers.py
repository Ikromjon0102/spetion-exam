import io

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.parsers.docx_parser import DocxParser
from app.parsers.pdf_parser import PdfParser


def _sample_docx_bytes() -> bytes:
    doc = Document()
    doc.add_paragraph("1. Toshkent qaysi davlatning poytaxti?")
    doc.add_paragraph("A) O'zbekiston")
    doc.add_paragraph("B) Qozog'iston")
    doc.add_paragraph("C) Qirg'iziston")
    doc.add_paragraph("D) Tojikiston")
    doc.add_paragraph("2-savol: 2+2 nechiga teng?")
    doc.add_paragraph("A) 3")
    doc.add_paragraph("B) 4")
    doc.add_paragraph("C) 5")
    doc.add_paragraph("D) 6")
    doc.add_paragraph("Javoblar: 1-A, 2-B")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_docx_parser_extracts_questions_and_uses_answer_key():
    questions = DocxParser().parse(_sample_docx_bytes())

    assert len(questions) == 2

    q1 = questions[0]
    assert "Toshkent" in q1.prompt
    assert len(q1.options) == 4
    assert q1.confidence == "high"
    correct = [o for o in q1.options if o.is_correct]
    assert len(correct) == 1
    assert correct[0].text == "O'zbekiston"

    q2 = questions[1]
    assert len(q2.options) == 4
    correct2 = [o for o in q2.options if o.is_correct]
    assert len(correct2) == 1
    assert correct2[0].text == "4"


def test_docx_parser_falls_back_to_bold_when_no_answer_key():
    doc = Document()
    doc.add_paragraph("1. Yer qaysi sayyoradan uchinchi?")
    p = doc.add_paragraph()
    run = p.add_run("A) Venera")
    run.bold = False
    p2 = doc.add_paragraph()
    run2 = p2.add_run("B) Yer")
    run2.bold = True
    doc.add_paragraph("C) Mars")
    doc.add_paragraph("D) Yupiter")

    buf = io.BytesIO()
    doc.save(buf)

    questions = DocxParser().parse(buf.getvalue())
    assert len(questions) == 1
    q = questions[0]
    assert q.confidence == "low"
    correct = [o for o in q.options if o.is_correct]
    assert len(correct) == 1
    assert correct[0].text == "Yer"


def test_docx_parser_reads_answer_key_from_table():
    """Regression test: a real uploaded exam had its answer key as a table
    ("Savol"/"Javob" row pair) instead of inline "Javoblar:" text or bold
    runs — python-docx only reads paragraph text by default, so this was
    silently ignored until docx_parser.py added a table pass."""
    doc = Document()
    doc.add_paragraph("1. Kompyuter nima uchun ishlatiladi?")
    doc.add_paragraph("A) Faqat musiqa tinglash uchun")
    doc.add_paragraph("B) Hujjatlar yaratish uchun")
    doc.add_paragraph("C) Faqat internet uchun")
    doc.add_paragraph("D) Faqat o'yin uchun")
    doc.add_paragraph("2. 2+2 nechiga teng?")
    doc.add_paragraph("A) 3")
    doc.add_paragraph("B) 4")
    doc.add_paragraph("C) 5")
    doc.add_paragraph("D) 6")

    table = doc.add_table(rows=2, cols=3)
    table.rows[0].cells[0].text = "Savol"
    table.rows[0].cells[1].text = "1"
    table.rows[0].cells[2].text = "2"
    table.rows[1].cells[0].text = "Javob"
    table.rows[1].cells[1].text = "D"
    table.rows[1].cells[2].text = "B"

    buf = io.BytesIO()
    doc.save(buf)

    questions = DocxParser().parse(buf.getvalue())
    assert len(questions) == 2

    q1_correct = [o for o in questions[0].options if o.is_correct]
    assert len(q1_correct) == 1
    assert q1_correct[0].text == "Faqat o'yin uchun"
    assert questions[0].confidence == "high"

    q2_correct = [o for o in questions[1].options if o.is_correct]
    assert len(q2_correct) == 1
    assert q2_correct[0].text == "4"


def test_docx_parser_skips_non_question_content():
    doc = Document()
    doc.add_paragraph("Matematika fanidan test savollari")
    doc.add_paragraph("1. 5+5 nechiga teng?")
    doc.add_paragraph("A) 9")
    doc.add_paragraph("B) 10")
    doc.add_paragraph("C) 11")
    doc.add_paragraph("D) 12")
    doc.add_paragraph("Javoblar: 1-B")

    buf = io.BytesIO()
    doc.save(buf)

    questions = DocxParser().parse(buf.getvalue())
    assert len(questions) == 1
    assert "5+5" in questions[0].prompt


def _sample_pdf_bytes(with_answer_key: bool = True) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 780
    c.setFont("Helvetica", 11)
    c.drawString(50, y, "1. Web-sahifalarni ko'rish uchun qanday dastur ishlatiladi?")
    y -= 20
    for letter, text in [("A", "Brauzer"), ("B", "Skanner"), ("C", "Printer"), ("D", "Klaviatura")]:
        c.drawString(70, y, f"{letter}) {text}")
        y -= 18
    y -= 10
    c.drawString(50, y, "2. HTML nima?")
    y -= 20
    for letter, text in [("A", "Dasturlash tili"), ("B", "Belgilash tili"), ("C", "Operatsion tizim"), ("D", "Antivirus")]:
        c.drawString(70, y, f"{letter}) {text}")
        y -= 18
    if with_answer_key:
        y -= 20
        c.drawString(50, y, "Javoblar: 1-A, 2-B")
    c.save()
    return buf.getvalue()


def test_pdf_parser_extracts_questions_and_uses_answer_key():
    questions = PdfParser().parse(_sample_pdf_bytes())

    assert len(questions) == 2
    assert questions[0].confidence == "high"
    q1_correct = [o for o in questions[0].options if o.is_correct]
    assert len(q1_correct) == 1
    assert q1_correct[0].text == "Brauzer"

    q2_correct = [o for o in questions[1].options if o.is_correct]
    assert len(q2_correct) == 1
    assert q2_correct[0].text == "Belgilash tili"


def test_pdf_parser_low_confidence_without_answer_key():
    # PDF bold-run detection is unreliable (see pdf_parser.py) — with no
    # "Javoblar:" section, options still parse but nothing is marked correct.
    questions = PdfParser().parse(_sample_pdf_bytes(with_answer_key=False))
    assert len(questions) == 2
    for q in questions:
        assert q.confidence == "low"
        assert not any(o.is_correct for o in q.options)


def test_pdf_parser_blank_page_never_crashes():
    """A scanned page with no extractable text falls through to the OCR
    path; per docs/spec.md section 4 that must never crash even when
    OCR finds nothing (e.g. tesseract isn't installed) — just 0 questions."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.showPage()  # a page with no text/content at all
    c.save()

    questions = PdfParser().parse(buf.getvalue())
    assert questions == []


def test_pdf_parser_strips_private_use_area_glyphs_from_embedded_fonts():
    """A real teacher's PDF (Word→PDF export with an embedded custom font)
    parsed to *zero* questions. Root cause: the font mapped an invisible
    spacing glyph into the Unicode Private Use Area, so pdfplumber's text
    extraction came back as e.g. "● A 198" instead of "● A 198" — the
    stray PUA codepoint sat directly between the option letter and the
    value with no whitespace, so PARSER_OPTION_PATTERNS' bullet pattern
    never matched. reportlab's base-14 fonts can't reproduce this exact
    byte-for-byte round-trip (they don't have real glyphs for "●"/PUA
    codepoints either, see the git history for the failed attempt), so this
    tests pdf_parser's PUA-stripping regex directly rather than faking a
    round-trip through actual PDF rendering.
    """
    from app.parsers.pdf_parser import _PUA_RE

    assert _PUA_RE.sub("", "● A 198") == "● A 198"
    assert _PUA_RE.sub("", "Hisoblang: 150 : 15 - 144 : 12 - 9") == "Hisoblang: 150 : 15 - 144 : 12 - 9"


def test_bullet_marker_option_pattern_and_space_separated_answer_table():
    """The same real PDF's answer key was a multi-column table ("Savol Javob
    Savol Javob ..." header, then rows like "1 B 6 B 11 A 16 B") rather than
    the inline "Javoblar: 1-A, 2-B" format — no dash/dot separator at all.
    Both new patterns (bullet-marker options, space-separated answer
    entries) covered directly against text_split.py's real functions.
    """
    from app.parsers.text_split import extract_answer_key, is_option_start, split_block, strip_option_marker

    assert is_option_start("● A 198")
    assert strip_option_marker("● A 198") == "198"

    block = [
        {"text": "1. Amallar tartibi:", "bold": False},
        {"text": "Hisoblang: 35 - 4 * 6 + 12", "bold": False},
        {"text": "● A 198", "bold": False},
        {"text": "● B 23", "bold": False},
        {"text": "● C 15", "bold": False},
        {"text": "● D 27", "bold": False},
    ]
    prompt, options = split_block(block)
    assert "Amallar tartibi" in prompt
    assert [o["text"] for o in options] == ["198", "23", "15", "27"]

    key_lines = [
        {"text": "Savol Javob Savol Javob Savol Javob Savol Javob", "bold": False},
        {"text": "1 B 6 B 11 A 16 B", "bold": False},
        {"text": "2 A 7 A 12 A 17 B", "bold": False},
    ]
    key = extract_answer_key(key_lines)
    assert key == {1: "B", 6: "B", 11: "A", 16: "B", 2: "A", 7: "A", 12: "A", 17: "B"}
