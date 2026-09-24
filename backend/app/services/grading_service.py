"""grade_attempt(db, attempt): joins student_answers.selected_option_id against
question_options.is_correct, sums points where correct -> attempt.score.
Sets attempt.max_score from exam.total_points. Called identically from both
the manual /submit endpoint and the Celery beat auto-submit sweep, so
behavior never diverges between the two paths.
"""

from sqlalchemy.orm import Session

from app.models.attempt import ExamAttempt
from app.models.exam import Exam, Question, QuestionOption


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
