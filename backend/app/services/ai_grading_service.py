"""AI grading for short_answer questions, via the Claude API.

grade_short_answer() compares the student's answer_text against the
TEACHER-SUPPLIED reference_answer only — never the question prompt alone,
and never the model's own outside knowledge — per the explicit design
confirmed with the user: a teacher must supply a model answer when
authoring a short_answer question specifically so grading has fixed ground
truth to compare against.

Called synchronously from grading_service.grade_attempt, identically from
both the manual /submit endpoint and the Celery beat auto-submit sweep
(same as MCQ scoring) — the AI grade counts immediately, a teacher can
override points_awarded/is_correct afterward in the review UI, per the
user's explicit "to'liq automatic amalga oshirsin, faqat ustoz keyin
tekshirib o'zgartira olsin" instruction.

Model choice: Haiku 4.5 — the user's own explicit pick after a cost
comparison (this runs per short-answer answer, per student, per exam: a
high-volume, low-complexity-per-call classification task, not one that
benefits from a larger model's reasoning).
"""

import logging

from anthropic import Anthropic, AnthropicError
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5"

_SYSTEM_PROMPT = (
    "Siz maktab o'qituvchisining yordamchisisiz. Sizga savol matni, "
    "o'qituvchi tomonidan berilgan namunaviy (mo'ljal) javob va "
    "o'quvchining yozgan javobi beriladi. Vazifangiz — o'quvchining "
    "javobini FAQAT namunaviy javobga mazmunan solishtirib baholash, "
    "o'zingizning bilimingizga yoki taxminingizga asoslanib emas. So'zma-so'z "
    "bir xil bo'lishi shart emas — mazmuni to'g'ri, muhim faktlar mos "
    "kelsa yetarli. score — 0.0 (butunlay noto'g'ri) dan 1.0 (to'liq "
    "to'g'ri) gacha, oraliq qiymatlar qisman to'g'ri javoblar uchun. "
    "feedback — o'zbek tilida, 1-2 gapli qisqa izoh."
)


class _ShortAnswerGrade(BaseModel):
    score: float
    feedback: str


_client: Anthropic | None = None


def _get_client() -> Anthropic | None:
    global _client
    if not settings.anthropic_api_key:
        return None
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def grade_short_answer(
    prompt_text: str, reference_answer: str, student_answer: str | None, max_points: float
) -> tuple[float, str]:
    """Returns (points_awarded, feedback), rounded to 2 decimals. Never
    raises — a single bad grading call (missing key, network error, rate
    limit, malformed response) must not break the whole exam submission;
    it falls back to 0 points with an explanatory feedback string so the
    teacher knows to grade that answer manually instead."""
    if not student_answer or not student_answer.strip():
        return 0.0, "O'quvchi javob yozmagan."

    client = _get_client()
    if client is None:
        return 0.0, "AI baholash sozlanmagan (ANTHROPIC_API_KEY yo'q) — ustoz qo'lda baholashi kerak."

    try:
        response = client.messages.parse(
            model=_MODEL,
            max_tokens=300,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Savol: {prompt_text}\n\n"
                        f"Namunaviy javob: {reference_answer}\n\n"
                        f"O'quvchining javobi: {student_answer}"
                    ),
                }
            ],
            output_format=_ShortAnswerGrade,
        )
        graded = response.parsed_output
        if graded is None:
            # output_format is supposed to guarantee valid, schema-matching
            # JSON, but a refusal or a max_tokens cutoff can still leave it
            # unset — treat exactly like any other grading failure.
            raise ValueError("empty parsed_output")
        score = max(0.0, min(1.0, graded.score))
        return round(score * max_points, 2), graded.feedback.strip()
    except (AnthropicError, ValueError):
        logger.exception("AI grading call failed")
        return 0.0, "AI baholashda xatolik yuz berdi — ustoz qo'lda tekshirib chiqishi kerak."
