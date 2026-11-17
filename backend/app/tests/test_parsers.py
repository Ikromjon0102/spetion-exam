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
    # exactly one bold option is a clear signal (the real teacher files mark
    # the correct answer this way and have no answer key at all)
    assert q.confidence == "high"
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
    from app.parsers.text_split import (
        extract_answer_key,
        is_option_start,
        make_line,
        parse_questions,
        strip_option_marker,
    )

    assert is_option_start("● A 198")
    assert strip_option_marker("● A 198") == "198"

    lines = [
        make_line(t)
        for t in [
            "1. Amallar tartibi:",
            "Hisoblang: 35 - 4 * 6 + 12",
            "● A 198",
            "● B 23",
            "● C 15",
            "● D 27",
        ]
    ]
    (question,) = parse_questions(lines, {})
    assert "Amallar tartibi" in question.prompt
    assert [o.text for o in question.options] == ["198", "23", "15", "27"]

    key_lines = [
        {"text": "Savol Javob Savol Javob Savol Javob Savol Javob", "bold": False},
        {"text": "1 B 6 B 11 A 16 B", "bold": False},
        {"text": "2 A 7 A 12 A 17 B", "bold": False},
    ]
    key = extract_answer_key(key_lines)
    assert key == {1: "B", 6: "B", 11: "A", 16: "B", 2: "A", 7: "A", 12: "A", 17: "B"}


def _docx_bytes(doc: Document) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_docx_parser_accepts_markers_without_a_space_after_them():
    """A real report: a 20-question file parsed as 19 because one question
    was typed "20.Savol" with no space — the marker went unrecognised and the
    question merged into the previous one."""
    doc = Document()
    doc.add_paragraph("19. Birinchi savol?")
    doc.add_paragraph("A.Bir")
    doc.add_paragraph("B) Ikki")
    doc.add_paragraph("20.Ikkinchi savol?")
    doc.add_paragraph("A.Uch")
    doc.add_paragraph("B.To'rt")
    doc.add_paragraph("Javoblar: 19-A, 20-B")

    questions = DocxParser().parse(_docx_bytes(doc))

    assert len(questions) == 2
    assert questions[1].prompt == "Ikkinchi savol?"
    assert [o.text for o in questions[1].options] == ["Uch", "To'rt"]
    assert [o.is_correct for o in questions[1].options] == [False, True]


def test_decimal_numbers_at_line_start_are_not_question_markers():
    doc = Document()
    doc.add_paragraph("1. Pi taxminan nechaga teng?")
    doc.add_paragraph("3.14 ga yaqin son qaysi?")
    doc.add_paragraph("A) 3")
    doc.add_paragraph("B) 4")
    doc.add_paragraph("Javoblar: 1-A")

    questions = DocxParser().parse(_docx_bytes(doc))

    assert len(questions) == 1
    assert "3.14 ga yaqin" in questions[0].prompt


def test_docx_parser_reconstructs_wordss_automatic_list_numbers():
    """Questions typed through Word's numbered-list button have no "1." in
    paragraph.text at all — python-docx only sees the bare question text, so
    every one used to merge into its predecessor."""
    doc = Document()
    for i in range(1, 4):
        doc.add_paragraph(f"Savol matni {i}?", style="List Number")
        doc.add_paragraph("A) Bir")
        doc.add_paragraph("B) Ikki")
    doc.add_paragraph("Javoblar: 1-A, 2-B, 3-A")

    questions = DocxParser().parse(_docx_bytes(doc))

    assert len(questions) == 3
    assert [q.prompt for q in questions] == ["Savol matni 1?", "Savol matni 2?", "Savol matni 3?"]
    assert [[o.is_correct for o in q.options] for q in questions] == [[True, False], [False, True], [True, False]]


# ---- real-world layouts (modelled on three teachers' actual files) ----------


def _line_with_bold_option(doc, prefix, options, bold_index):
    """One paragraph holding several options, only one of them a bold run —
    how the chemistry/biology files mark the correct answer."""
    p = doc.add_paragraph()
    for i, text in enumerate(options):
        run = p.add_run(f"{chr(65 + i)}) {text}" + ("\t" if i < len(options) - 1 else ""))
        run.bold = i == bold_index
    return p


def test_docx_inline_options_with_one_bold_run_mark_the_correct_one():
    doc = Document()
    doc.add_paragraph("1. Qaysi son eng katta?")
    _line_with_bold_option(doc, "", ["4 ta", "6 ta", "8 ta", "10 ta"], bold_index=2)
    doc.add_paragraph("2. Keyingi savol?")
    _line_with_bold_option(doc, "", ["a", "b", "c", "d"], bold_index=0)

    questions = DocxParser().parse(_docx_bytes(doc))

    assert len(questions) == 2
    assert [o.text for o in questions[0].options] == ["4 ta", "6 ta", "8 ta", "10 ta"]
    assert [o.is_correct for o in questions[0].options] == [False, False, True, False]
    assert [o.is_correct for o in questions[1].options] == [True, False, False, False]
    assert questions[0].confidence == "high"


def test_a_question_mentioning_javoblar_does_not_cut_the_file_short():
    """"To'g'ri javoblar sonini toping" contains the word the answer-key
    header looks for — the rest of the file used to vanish after it."""
    doc = Document()
    for n in (1, 2, 3):
        text = "To'g'ri javoblar sonini toping?" if n == 2 else f"Savol {n}?"
        doc.add_paragraph(f"{n}. {text}")
        for letter in "ABCD":
            doc.add_paragraph(f"{letter}) variant")
    doc.add_paragraph("Javoblar: 1-A, 2-B, 3-C")

    questions = DocxParser().parse(_docx_bytes(doc))

    assert len(questions) == 3
    assert [[o.is_correct for o in q.options].index(True) for q in questions] == [0, 1, 2]


def test_statement_lists_inside_a_question_are_not_split_into_questions():
    """"1) ... 2) ... 3) ..." statements precede the options; they used to be
    torn into fake questions, taking the real question's text with them."""
    doc = Document()
    doc.add_paragraph("1. Quyidagilardan shaharlarni ko'rsating.")
    doc.add_paragraph("1) Toshkent")
    doc.add_paragraph("2) Samarqand")
    doc.add_paragraph("3) Amudaryo")
    doc.add_paragraph("A) 1,2")
    doc.add_paragraph("B) 2,3")
    doc.add_paragraph("2.Keyingi savol?")
    doc.add_paragraph("1)bir  2)ikki  3)uch")
    doc.add_paragraph("A)1,2   B)2,3")
    doc.add_paragraph("Javoblar: 1-A, 2-B")

    questions = DocxParser().parse(_docx_bytes(doc))

    assert len(questions) == 2
    assert "Toshkent" in questions[0].prompt and "Amudaryo" in questions[0].prompt
    assert [o.text for o in questions[0].options] == ["1,2", "2,3"]
    assert "1)bir" in questions[1].prompt
    assert [o.is_correct for o in questions[1].options] == [False, True]


def test_lowercase_and_stray_uppercase_markers_in_a_statement_line_are_text():
    doc = Document()
    doc.add_paragraph("1. Tartib bilan joylashtiring.")
    doc.add_paragraph("a)og'iz B)ichak d)halqum e)oshqozon")
    for letter, text in zip("ABCD", ["a,d,b,e", "a,b,d,e", "d,a,b,e", "e,d,b,a"]):
        doc.add_paragraph(f"{letter}){text}")
    doc.add_paragraph("Javoblar: 1-B")

    (q,) = DocxParser().parse(_docx_bytes(doc))

    assert "a)og'iz" in q.prompt
    assert [o.text for o in q.options] == ["a,d,b,e", "a,b,d,e", "d,a,b,e", "e,d,b,a"]


def test_cyrillic_lookalike_option_letters_are_read_as_latin():
    doc = Document()
    doc.add_paragraph("1. Savol?")
    doc.add_paragraph("А) bir\tВ) ikki")  # Cyrillic А and В
    doc.add_paragraph("C) uch\tD) to'rt")
    doc.add_paragraph("Javoblar: 1-B")

    (q,) = DocxParser().parse(_docx_bytes(doc))

    assert [o.text for o in q.options] == ["bir", "ikki", "uch", "to'rt"]
    assert [o.is_correct for o in q.options] == [False, True, False, False]


def test_five_options_and_lowercase_answer_key():
    doc = Document()
    doc.add_paragraph("1. Savol?")
    for letter in "ABCDE":
        doc.add_paragraph(f"{letter}) {letter.lower()}")
    doc.add_paragraph("Javoblar: 1-e")

    (q,) = DocxParser().parse(_docx_bytes(doc))

    assert len(q.options) == 5
    assert [o.is_correct for o in q.options] == [False, False, False, False, True]


def test_questions_inside_a_word_table_are_read():
    doc = Document()
    table = doc.add_table(rows=1, cols=1)
    cell = table.cell(0, 0)
    cell.paragraphs[0].text = "1. Jadval ichidagi savol?"
    for letter in "ABCD":
        cell.add_paragraph(f"{letter}) {letter}")
    doc.add_paragraph("Javoblar: 1-C")

    (q,) = DocxParser().parse(_docx_bytes(doc))

    assert q.prompt == "Jadval ichidagi savol?"
    assert [o.is_correct for o in q.options] == [False, False, True, False]


def test_subscripts_survive_as_rich_text_and_plain_text_stays_plain():
    doc = Document()
    p = doc.add_paragraph("1. ")
    p.add_run("H")
    p.add_run("2").font.subscript = True
    p.add_run("SO4 qaysi?")
    doc.add_paragraph("A) bir")
    doc.add_paragraph("B) ikki")
    doc.add_paragraph("2. Oddiy savol?")
    doc.add_paragraph("A) bir")
    doc.add_paragraph("B) ikki")

    q1, q2 = DocxParser().parse(_docx_bytes(doc))

    assert q1.prompt == "<!--sp-rich--><p>H<sub>2</sub>SO4 qaysi?</p>"
    assert q2.prompt == "Oddiy savol?"  # no formatting -> exactly the plain text as before


def test_a_word_equation_is_flagged_not_silently_dropped():
    from docx.oxml import parse_xml

    ns = (
        'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    )
    doc = Document()
    p = doc.add_paragraph("1. Hisoblang: ")
    p._p.append(parse_xml(f"<m:oMath {ns}><m:r><m:t>x+1</m:t></m:r></m:oMath>"))
    for letter in "ABCD":
        doc.add_paragraph(f"{letter}) {letter}")
    doc.add_paragraph("Javoblar: 1-A")

    (q,) = DocxParser().parse(_docx_bytes(doc))

    assert "x+1" in q.prompt
    assert q.confidence == "low"
    assert "formula_lost" in q.warnings


def _pdf_with(lines):
    """lines: [(x, y, size, text)] drawn in Times."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for x, y, size, text in lines:
        c.setFont("Helvetica", size)
        c.drawString(x, y, text)
    c.save()
    return buf.getvalue()


def test_pdf_exponents_are_recovered_and_options_on_one_line_split():
    # "30" then a small raised "15" -> 30^15, and "A)34 B)16 C)13 D)10" on one line
    from reportlab.pdfbase.pdfmetrics import stringWidth

    pdf = _pdf_with(
        [
            (50, 780, 14, "7. Hisoblang 30"),
            (50 + stringWidth("7. Hisoblang 30", "Helvetica", 14), 786, 9, "15"),
            (50, 760, 14, "A)34 B)16 C)13 D)10"),
            (50, 730, 14, "8. Ikkinchi savol?"),
            (50, 710, 14, "A)1 B)2 C)3 D)4"),
        ]
    )
    q1, q2 = PdfParser().parse(pdf)

    assert "30<sup>15</sup>" in q1.prompt
    assert [o.text for o in q1.options] == ["34", "16", "13", "10"]
    assert [o.text for o in q2.options] == ["1", "2", "3", "4"]
    assert q1.confidence == "low" and "no_correct_answer" in q1.warnings  # no key, no bold in a PDF


def test_pdf_running_header_is_not_glued_onto_the_last_option():
    pages = []
    for page in range(2):
        pages.append(
            [
                (50, 800, 11, "I-CHORAK MATEMATIKA"),
                (50, 760, 12, f"{page + 1}. Savol?"),
                (50, 740, 12, "A) bir"),
                (50, 724, 12, "B) ikki"),
                (50, 40, 10, str(page + 1)),  # page number
            ]
        )
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for page in pages:
        for x, y, size, text in page:
            c.setFont("Helvetica", size)
            c.drawString(x, y, text)
        c.showPage()
    c.save()

    questions = PdfParser().parse(buf.getvalue())

    assert [[o.text for o in q.options] for q in questions] == [["bir", "ikki"], ["bir", "ikki"]]
