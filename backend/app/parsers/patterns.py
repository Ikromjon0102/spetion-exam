# Tunable without touching parsing logic elsewhere. Tried in order.
PARSER_QUESTION_PATTERNS = [
    r"^\s*\d+[\.\)]\s+",       # "1. " or "1) "
    r"^\s*\d+-savol[:.]?\s*",  # "1-savol:"
]

PARSER_OPTION_PATTERNS = [
    r"^\s*[A-D][\.\)]\s+",
    r"^\s*[a-d][\.\)]\s+",
]

# A trailing answer-key section, e.g. "Javoblar: 1-B, 2-A, 3-C" — more
# reliable than in-line bold/asterisk detection when present.
ANSWER_KEY_HEADER_PATTERN = r"(?i)javoblar\s*[:.]?"
ANSWER_KEY_ENTRY_PATTERN = r"(\d+)\s*[-.]\s*([A-D])"
