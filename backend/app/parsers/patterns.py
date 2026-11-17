# Tunable without touching parsing logic elsewhere.
#
# A question marker is "1." / "1)" / "20.Savol" / "10)Ona va erkak..." — the
# space after it is optional on purpose: teachers routinely type it without
# one, and a marker the parser misses silently merges that question into the
# previous one. The (?!\d) after a "." keeps decimals like "3.14" or "1.5 m"
# from being read as question 3 / question 1; a ")" needs no such guard.
PARSER_QUESTION_PATTERNS = [
    r"^\s*(\d{1,4})\s*(?:\.(?!\d)|\))\s*",  # "1. ", "1) ", "20.Savol", "10)Ona"
    r"^\s*(\d{1,4})-savol[:.]?\s*",         # "1-savol:"
]

# Option letters a question may use. The UI lets a teacher add up to 8
# options, so a 5-option (E) test must parse too.
OPTION_LETTERS = "ABCDEFGH"

# A trailing answer-key section: "Javoblar: 1-B, 2-A" — more reliable than
# bold detection when present. The header must START the line (a question
# that merely contains the word, "To'g'ri javoblar sonini toping", is not a
# header — that used to cut the whole rest of the file off).
ANSWER_KEY_HEADER_PATTERN = r"(?i)^\s*(?:javoblar|javob\s+kaliti|kalitlar|answers?)\b[\s:.\-]*(.*)$"

ANSWER_KEY_ENTRY_PATTERNS = [
    r"(\d+)\s*[-.:)]\s*([A-Ha-h])\b",
    # A multi-column answer table with no separator at all, e.g. a PDF's
    # "Savol Javob Savol Javob ..." header row followed by data rows like
    # "1 B 6 B 11 A 16 B" (four question/answer pairs per line, plain-text
    # extraction of what was a real table in the source document). Only
    # tried when the dash/dot pattern finds nothing at all on that line.
    r"(\d+)\s+([A-Ha-h])\b",
]
