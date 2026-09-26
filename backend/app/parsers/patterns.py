# Tunable without touching parsing logic elsewhere. Tried in order.
PARSER_QUESTION_PATTERNS = [
    r"^\s*\d+[\.\)]\s+",       # "1. " or "1) "
    r"^\s*\d+-savol[:.]?\s*",  # "1-savol:"
]

PARSER_OPTION_PATTERNS = [
    r"^\s*[A-D][\.\)]\s+",
    r"^\s*[a-d][\.\)]\s+",
    # A bullet-marker option, e.g. "● A 198" — no punctuation after the
    # letter at all, a real format a teacher's PDF used (options are just
    # "bullet, letter, space, value"). Kept as its own pattern rather than
    # widening the ones above so "A." / "A)" still requires the punctuation
    # — a bare "A " with no marker at all is too easy to false-positive on
    # ordinary prose.
    r"^\s*[●•]\s*[A-D]\s+",
]

# A trailing answer-key section, e.g. "Javoblar: 1-B, 2-A, 3-C" — more
# reliable than in-line bold/asterisk detection when present.
ANSWER_KEY_HEADER_PATTERN = r"(?i)javoblar\s*[:.]?"
ANSWER_KEY_ENTRY_PATTERNS = [
    r"(\d+)\s*[-.]\s*([A-D])",
    # A multi-column answer table with no separator at all, e.g. a PDF's
    # "Savol Javob Savol Javob ..." header row followed by data rows like
    # "1 B 6 B 11 A 16 B" (four question/answer pairs per line, plain-text
    # extraction of what was a real table in the source document). Tried
    # second since it's the more permissive pattern — order matters here,
    # first-match-wins per position would be ideal but findall doesn't
    # dedupe across patterns, so extract_answer_key only falls back to this
    # one when the dash/dot pattern finds nothing at all on that line.
    r"(\d+)\s+([A-D])\b",
]
