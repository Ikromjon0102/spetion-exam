"""Shared block-splitting helpers used by both docx_parser and pdf_parser.

Each input line is `{"text": str, "bold": bool}` — pdf_parser always passes
bold=False since PDF bold-run detection is unreliable (see pdf_parser.py).
"""

import re

from app.parsers.patterns import (
    ANSWER_KEY_ENTRY_PATTERN,
    ANSWER_KEY_HEADER_PATTERN,
    PARSER_OPTION_PATTERNS,
    PARSER_QUESTION_PATTERNS,
)


def _first_match(patterns: list[str], text: str) -> re.Match | None:
    for pattern in patterns:
        m = re.match(pattern, text)
        if m:
            return m
    return None


def is_question_start(text: str) -> bool:
    return _first_match(PARSER_QUESTION_PATTERNS, text) is not None


def is_option_start(text: str) -> bool:
    return _first_match(PARSER_OPTION_PATTERNS, text) is not None


def strip_question_marker(text: str) -> str:
    for pattern in PARSER_QUESTION_PATTERNS:
        stripped = re.sub(pattern, "", text, count=1)
        if stripped != text:
            return stripped.strip()
    return text.strip()


def strip_option_marker(text: str) -> str:
    for pattern in PARSER_OPTION_PATTERNS:
        stripped = re.sub(pattern, "", text, count=1)
        if stripped != text:
            return stripped.strip()
    return text.strip()


def split_off_answer_key(lines: list[dict]) -> tuple[list[dict], list[dict]]:
    """Splits at the first "Javoblar:" header so the trailing answer-key
    section is never mistaken for a continuation of the last question's
    last option."""
    for i, line in enumerate(lines):
        if re.search(ANSWER_KEY_HEADER_PATTERN, line["text"]):
            return lines[:i], lines[i:]
    return lines, []


def extract_answer_key(key_lines: list[dict]) -> dict[int, str]:
    """key_lines: the slice returned as the second element of
    split_off_answer_key. Returns {question_number: 'A'|'B'|'C'|'D'}."""
    key: dict[int, str] = {}
    for line in key_lines:
        for num, letter in re.findall(ANSWER_KEY_ENTRY_PATTERN, line["text"]):
            key[int(num)] = letter.upper()
    return key


def split_into_blocks(lines: list[dict]) -> list[list[dict]]:
    """Splits into question blocks on a numbering pattern match."""
    blocks: list[list[dict]] = []
    current: list[dict] = []
    for line in lines:
        if is_question_start(line["text"]):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def question_number(block: list[dict]) -> int | None:
    if not block:
        return None
    m = re.match(r"^\s*(\d+)[\.\)]", block[0]["text"]) or re.match(r"^\s*(\d+)-savol", block[0]["text"])
    return int(m.group(1)) if m else None


def split_block(block: list[dict]) -> tuple[str, list[dict]]:
    """Within one question block, separates the prompt from option lines.
    Returns (prompt_text, option_lines) where option_lines keep their bold
    flag (OR'd across any wrapped continuation lines)."""
    prompt_parts: list[str] = []
    options: list[dict] = []
    for line in block:
        text = line["text"]
        if is_option_start(text):
            options.append({"text": strip_option_marker(text), "bold": line["bold"]})
        elif options:
            options[-1]["text"] += " " + text.strip()
            options[-1]["bold"] = options[-1]["bold"] or line["bold"]
        else:
            prompt_parts.append(text)
    prompt = strip_question_marker(" ".join(prompt_parts).strip())
    return prompt, options
