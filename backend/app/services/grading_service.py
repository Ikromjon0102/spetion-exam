"""grade_attempt(db, attempt): for mcq answers, joins
student_answers.selected_option_id against question_options.is_correct; for
short_answer, calls ai_grading_service against the teacher-supplied
reference_answer. Sums points -> attempt.score, sets attempt.max_score from
exam.total_points. Called identically from both the manual /submit endpoint
and the Celery beat auto-submit sweep, so behavior never diverges between
the two paths — including the AI grading call, which runs inline here
rather than as a separate async step (see ai_grading_service's docstring).
"""

from sqlalchemy.orm import Session

from app.core import rich_text
from app.models.attempt import ExamAttempt
from app.models.exam import Exam, Question, QuestionOption, QuestionType
from app.services import ai_grading_service


def grade_attempt(db: Session, attempt: ExamAttempt) -> ExamAttempt:
    exam = db.get(Exam, attempt.exam_id)
    questions = {q.id: q for q in exam.questions}
    options_by_id: dict[int, QuestionOption] = {
        opt.id: opt for q in exam.questions for opt in q.options
    }

    total_score = 0.0
    for answer in attempt.answers:
        question = questions.get(answer.question_id)
        if question is None:
            continue
        if question.question_type == QuestionType.short_answer:
            points, feedback = ai_grading_service.grade_short_answer(
                # the model should read the question, not its HTML markup
                prompt_text=rich_text.to_plain_text(question.prompt_text),
                reference_answer=question.reference_answer or "",
                student_answer=answer.answer_text,
                max_points=float(question.points),
            )
            answer.points_awarded = points
            answer.is_correct = points >= float(question.points)
            answer.ai_feedback = feedback
            answer.graded_by = "ai"
        else:
            if answer.selected_option_id is not None:
                option = options_by_id.get(answer.selected_option_id)
                is_correct = bool(option and option.is_correct)
            else:
                is_correct = False
            answer.is_correct = is_correct
            answer.points_awarded = float(question.points) if is_correct else 0.0
        total_score += answer.points_awarded

    attempt.score = total_score
    attempt.max_score = float(exam.total_points or 0)
    db.commit()
    db.refresh(attempt)
    return attempt


def recompute_score_from_answers(db: Session, attempt: ExamAttempt) -> ExamAttempt:
    """Sums the already-graded answers' points_awarded into attempt.score
    without re-grading anything — used after a teacher manually overrides
    one short_answer's points_awarded (admin_exams.py's override endpoint),
    so recomputing the total doesn't stomp that override by re-invoking AI
    grading on every answer via grade_attempt."""
    attempt.score = sum(float(a.points_awarded) for a in attempt.answers if a.points_awarded is not None)
    db.commit()
    db.refresh(attempt)
    return attempt
