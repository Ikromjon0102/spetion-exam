"""The shared engine behind docx_parser and pdf_parser: turns a list of lines
into questions.

A line is {"text": str, "fmt": list[int] | None, "ocr": bool, "flags": set}.
`fmt` is one bit-set per character (BOLD / SUB / SUP) so a correct answer
marked by bold on ONE option of an inline row ("A)4 ta  B)6 ta  C)8 ta") can
still be told apart, and exponents/subscripts survive as rich text. Lines
without `fmt` (hand-built ones in tests) may carry a plain "bold" flag.

How it reads a file — built against real teacher files, not guesses:
  * Options may be one per line, several per line ("A)34 B)16 C)13 D)10"),
    split by tabs/spaces, and may mix Latin and Cyrillic look-alike letters
    ("А) ... В) ..." with a Cyrillic А and В). Option markers are only
    accepted in sequence (A, then B, then C ...) and only from the start of
    a line, so "a)og'iz B)ichak d)halqum" inside a question's own statement
    list is text, not options.
  * A new question starts at a number marker, but only once the current one
    has an option — statements "1) ... 2) ... 3) ..." come BEFORE the
    options, and used to be torn into fake questions.
  * The correct answer is the key's letter if there is one, else the single
    bold option, else unknown (never guessed).
"""

import html
import re
import unicodedata

from app.core import rich_text
from app.parsers.base import ParsedOption, ParsedQuestion
from app.parsers.patterns import (
    ANSWER_KEY_ENTRY_PATTERNS,
    ANSWER_KEY_HEADER_PATTERN,
    OPTION_LETTERS,
    PARSER_QUESTION_PATTERNS,
)

BOLD, SUB, SUP = 1, 2, 4

# Cyrillic letters that look exactly like Latin option letters. Teachers mix
# them freely ("А) ... В) ..."), and to a human they are the same letter.
_LOOKALIKE = str.maketrans("АВСЕН", "ABCEH")
_COMBINING = re.compile(r"[̀-ͯ]")
_MATH_ALNUM = re.compile("[\U0001d400-\U0001d7ff]")

_OPT_MARK = re.compile(r"(?:(?<=\s)|^)(?:[●•]\s*([A-H])(?=\s)|([A-H])[\.\)])")
_OPT_MARK_LOWER = re.compile(r"(?:(?<=\s)|^)(?:[●•]\s*([a-h])(?=\s)|([a-h])[\.\)])")
_OPT_START = re.compile(r"^\s*(?:[●•]\s*([A-H])(?=\s)|([A-H])[\.\)])")

_KEY_HEADER = re.compile(ANSWER_KEY_HEADER_PATTERN)
_KEY_ENTRIES = re.compile(r"(?:\d+\s*[-.:)]?\s*[A-Ha-h][\s,;.]*)+")


# ---------------------------------------------------------------- lines ----


def make_line(text: str, fmt: list[int] | None = None, ocr: bool = False, flags: set | None = None) -> dict | None:
    """A normalised line, or None if nothing is left of it. Drops combining
    marks (a PDF's overline over a number is a line of its own made only of
    them), turns math-italic letters (𝑎) into plain ones, strips the edges —
    keeping `fmt` in step with every change."""
    fmt = list(fmt) if fmt is not None else [0] * len(text)
    out_text: list[str] = []
    out_fmt: list[int] = []
    for ch, bits in zip(text, fmt):
        if _COMBINING.match(ch):
            continue
        if _MATH_ALNUM.match(ch):
            ch = unicodedata.normalize("NFKC", ch)
        out_text.append(ch)
        out_fmt.append(bits)
    joined = "".join(out_text)
    lead = len(joined) - len(joined.lstrip())
    trail = len(joined.rstrip())
    joined, out_fmt = joined[lead:trail], out_fmt[lead:trail]
    if not joined:
        return None
    return {"text": joined, "fmt": out_fmt, "ocr": ocr, "flags": set(flags or ())}


def _fmt_of(line: dict) -> list[int]:
    if line.get("fmt") is not None:
        return line["fmt"]
    return [BOLD if line.get("bold") else 0] * len(line["text"])


# --------------------------------------------------------------- markers ----


def _norm(text: str) -> str:
    return text.translate(_LOOKALIKE)


def _question_match(text: str) -> re.Match | None:
    for pattern in PARSER_QUESTION_PATTERNS:
        m = re.match(pattern, text)
        if m:
            return m
    return None


def is_question_start(text: str) -> bool:
    return _question_match(text) is not None


def is_option_start(text: str) -> bool:
    return _OPT_START.match(_norm(text)) is not None


def strip_question_marker(text: str) -> str:
    m = _question_match(text)
    return text[m.end():].strip() if m else text.strip()


def strip_option_marker(text: str) -> str:
    m = _OPT_START.match(_norm(text))
    return text[m.end():].strip() if m else text.strip()


def _option_segments(text: str, expected: int, lower: bool) -> list[tuple[int, int, int]]:
    """(marker_start, marker_end, letter_index) for each option on this line,
    or [] if the line isn't an option line. The line must start with the
    marker of the option expected next, and further markers are only taken in
    sequence."""
    pattern = _OPT_MARK_LOWER if lower else _OPT_MARK
    segments: list[tuple[int, int, int]] = []
    for m in pattern.finditer(_norm(text) if not lower else text):
        letter = (m.group(1) or m.group(2)).upper()
        index = OPTION_LETTERS.index(letter)
        want = expected + len(segments)
        if not segments and m.start() != 0:
            return []
        if index == want and want < len(OPTION_LETTERS):
            segments.append((m.start(), m.end(), index))
    return segments


# ------------------------------------------------------------ answer key ----


def split_off_answer_key(lines: list[dict]) -> tuple[list[dict], list[dict]]:
    """Splits at the answer-key header so the key is never read as part of
    the last option. A header is a line that STARTS with "Javoblar" and has
    nothing after it but key entries ("Javoblar: 1-B, 2-A") — a question
    that only contains the word is not one."""
    for i, line in enumerate(lines):
        m = _KEY_HEADER.match(line["text"])
        if m and (not m.group(1).strip() or _KEY_ENTRIES.fullmatch(m.group(1).strip())):
            return lines[:i], lines[i:]
    return lines, []


def extract_answer_key(key_lines: list[dict]) -> dict[int, str]:
    """{question_number: 'A'..'H'} from the lines split_off_answer_key
    returned. Per line, the first pattern that finds anything wins — the
    separator-less table pattern is more permissive, so the stricter one
    gets first refusal."""
    key: dict[int, str] = {}
    for line in key_lines:
        for pattern in ANSWER_KEY_ENTRY_PATTERNS:
            matches = re.findall(pattern, line["text"])
            if matches:
                for num, letter in matches:
                    key[int(num)] = letter.upper()
                break
    return key


# ----------------------------------------------------------- rich output ----


def _html_runs(text: str, fmt: list[int]) -> str:
    """Escaped HTML for one line, with <sub>/<sup> where the source had them."""
    out: list[str] = []
    i = 0
    while i < len(text):
        kind = fmt[i] & (SUB | SUP)
        j = i
        while j < len(text) and (fmt[j] & (SUB | SUP)) == kind:
            j += 1
        chunk = html.escape(text[i:j], quote=False)
        out.append(f"<sub>{chunk}</sub>" if kind == SUB else f"<sup>{chunk}</sup>" if kind == SUP else chunk)
        i = j
    return "".join(out)


def _has_script(fmt: list[int]) -> bool:
    return any(bits & (SUB | SUP) for bits in fmt)


def _compose(parts: list[tuple[str, list[int]]], joiner: str) -> str:
    """Plain text when no line has a sub/superscript (exactly as before);
    otherwise rich text, so "3015^3016" doesn't come out as "30153016"."""
    if not any(_has_script(fmt) for _, fmt in parts):
        return joiner.join(text for text, _ in parts).strip()
    body = "".join(f"<p>{_html_runs(text, fmt)}</p>" for text, fmt in parts)
    return rich_text.sanitize(rich_text.RICH_PREFIX + body)


# ----------------------------------------------------------- the engine ----


class _Draft:
    def __init__(self, number: int | None) -> None:
        self.number = number
        self.prompt: list[tuple[str, list[int]]] = []
        self.options: list[dict] = []  # {"text", "fmt"}
        self.ocr = False
        self.flags: set[str] = set()


def _lowercase_mode(lines: list[dict]) -> bool:
    """A file whose options are written "a) b) c) d)" (and never "A) B)") —
    otherwise lowercase markers are just text, as in "a)og'iz b)ichak" lists
    inside a question."""
    upper = sum(1 for ln in lines if _OPT_START.match(_norm(ln["text"])))
    lower = sum(1 for ln in lines if re.match(r"^\s*[a-d]\)\s", ln["text"]))
    return upper == 0 and lower > 0


def parse_questions(lines: list[dict], answer_key: dict[int, str]) -> list[ParsedQuestion]:
    lines = [ln for ln in lines if ln is not None]
    lower = _lowercase_mode(lines)
    drafts: list[_Draft] = []
    cur: _Draft | None = None

    for line in lines:
        text = line["text"]
        fmt = _fmt_of(line)

        if cur is not None:
            segments = _option_segments(text, len(cur.options), lower)
            if segments:
                for k, (start, end, _index) in enumerate(segments):
                    stop = segments[k + 1][0] if k + 1 < len(segments) else len(text)
                    seg_text, seg_fmt = text[end:stop], fmt[end:stop]
                    lead = len(seg_text) - len(seg_text.lstrip())
                    seg_text, seg_fmt = seg_text.strip(), seg_fmt[lead:lead + len(seg_text.strip())]
                    # bold is judged on the marker too ("B) ozon" bold as a whole)
                    judged = fmt[start:stop]
                    letters = [b for ch, b in zip(text[start:stop], judged) if not ch.isspace()]
                    bold = bool(letters) and sum(1 for b in letters if b & BOLD) / len(letters) >= 0.5
                    cur.options.append({"text": seg_text, "fmt": seg_fmt, "bold": bold})
                cur.ocr = cur.ocr or line.get("ocr", False)
                cur.flags |= line.get("flags", set())
                continue

        m = _question_match(text)
        # Statements ("1) ... 2) ...") come before the options, so a number
        # marker only starts a question once the current one HAS an option.
        if m and (cur is None or cur.options):
            number = int(m.group(1))
            cur = _Draft(number)
            drafts.append(cur)
            rest = text[m.end():]
            lead = len(rest) - len(rest.lstrip())
            cur.prompt.append((rest.lstrip(), fmt[m.end() + lead:]))
            cur.ocr = line.get("ocr", False)
            cur.flags |= line.get("flags", set())
            continue

        if cur is None:
            continue  # title / preamble before the first question
        cur.ocr = cur.ocr or line.get("ocr", False)
        cur.flags |= line.get("flags", set())
        if cur.options:
            last = cur.options[-1]
            last["text"] += " " + text
            last["fmt"] = last["fmt"] + [0] + fmt
            last["bold"] = last["bold"] or any(b & BOLD for b in fmt)
        else:
            cur.prompt.append((text, fmt))

    return [_finish(d, answer_key) for d in drafts if any(t for t, _ in d.prompt)]


def _finish(d: _Draft, answer_key: dict[int, str]) -> ParsedQuestion:
    prompt_parts = [(t, f) for t, f in d.prompt if t]
    prompt = _compose(prompt_parts, "\n")

    correct: int | None = None
    resolved_by = None
    letter = answer_key.get(d.number) if d.number is not None else None
    if letter and OPTION_LETTERS.index(letter) < len(d.options):
        correct, resolved_by = OPTION_LETTERS.index(letter), "key"
    else:
        bold = [i for i, o in enumerate(d.options) if o["bold"]]
        if len(bold) == 1:
            correct, resolved_by = bold[0], "bold"

    options = [
        ParsedOption(text=_compose([(o["text"], o["fmt"])], " "), is_correct=(i == correct))
        for i, o in enumerate(d.options)
    ]

    warnings: list[str] = []
    if correct is None:
        warnings.append("no_correct_answer")
    if len(options) < 2:
        warnings.append("few_options")
    if d.ocr:
        warnings.append("ocr")
    if "formula" in d.flags:
        warnings.append("formula_lost")
    if "image" in d.flags:
        warnings.append("image_lost")

    confidence = "high" if (resolved_by and len(options) >= 2 and not d.ocr and not (d.flags & {"formula", "image"})) else "low"
    return ParsedQuestion(prompt=prompt, options=options, confidence=confidence, warnings=warnings)
