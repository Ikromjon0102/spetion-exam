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
