/**
 * "O'quvchi ko'zi bilan ko'rish": the exam exactly as a student will see it,
 * for the teacher to check before publishing — the same ExamScreen component
 * the real exam renders, fed from the editor's data instead of an attempt.
 *
 * Nothing here touches the student API: no attempt is created, no answer is
 * saved, nothing is submitted. Answers picked while trying it out live in
 * this page's state and are gone on leaving. The correct answers are never
 * shown, just as for a student.
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getExamDetail, type ExamDetail } from "../../api/adminApi";
import type { AttemptQuestion, ExamSectionInfo } from "../../api/studentApi";
import { Button, Modal } from "../../components/ui";
import ExamScreen, { groupQuestions, isAnswered, type Answers, type TextAnswers } from "../student/ExamScreen";
import { useLanguage } from "../../i18n/LanguageContext";
import { errorDetail } from "../../utils/errorDetail";
import { formatPoints } from "../../utils/formatPoints";

export default function ExamPreviewPage() {
  const { examId } = useParams();
  const id = Number(examId);
  const { t } = useLanguage();
  const navigate = useNavigate();

  const [exam, setExam] = useState<ExamDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [textAnswers, setTextAnswers] = useState<TextAnswers>({});
  const [remaining, setRemaining] = useState(0);
  const [submitOpen, setSubmitOpen] = useState(false);

  useEffect(() => {
    getExamDetail(id)
      .then((detail) => {
        setExam(detail);
        setRemaining(detail.duration_minutes * 60);
      })
      .catch((e) => setError(errorDetail(e, t("review.loadError"))));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // The clock runs so the bar looks and behaves as it will; at zero it simply
  // stops — there is nothing to submit.
  useEffect(() => {
    if (!exam) return;
    const interval = setInterval(() => setRemaining((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(interval);
  }, [exam]);

  // A chorak exam's blocks in the paper's order (a block's teacher gets only
  // their own — that is all the editor's data holds for them). Only blocks
  // that have questions, so an unwritten block isn't an empty tab.
  const sections: ExamSectionInfo[] = useMemo(() => {
    if (!exam) return [];
    return exam.sections
      .filter((s) => exam.questions.some((q) => q.section_id === s.id))
      .map((s) => ({
        id: s.id,
        subject_name: s.subject_name,
        kind: s.kind,
        question_count: s.question_count,
        points_per_question: s.points_per_question,
      }));
  }, [exam]);

  const questions: AttemptQuestion[] = useMemo(() => {
    if (!exam) return [];
    const order = new Map(sections.map((s, i) => [s.id, i]));
    return [...exam.questions]
      .filter((q) => sections.length === 0 || (q.section_id !== null && order.has(q.section_id)))
      .sort((a, b) => (order.get(a.section_id ?? -1) ?? 0) - (order.get(b.section_id ?? -1) ?? 0) || a.order_index - b.order_index)
      .map((q) => ({
        id: q.id,
        section_id: q.section_id,
        order_index: q.order_index,
        question_type: q.question_type,
        prompt_text: q.prompt_text,
        prompt_image_key: q.prompt_image_key,
        points: q.points,
        // is_correct is deliberately dropped: a student never receives it
        options: q.options.map((o) => ({
          id: o.id,
          order_index: o.order_index,
          option_text: o.option_text,
          option_image_key: o.option_image_key,
        })),
        selected_option_id: null,
        answer_text: null,
      }));
  }, [exam, sections]);

  const back = `/admin/exams/${id}/review`;

  if (error || !exam) {
    return (
      <div className="page">
        {error ? (
          <p role="alert" style={{ color: "var(--danger)", marginBottom: "var(--space-4)" }}>
            {error}
          </p>
        ) : (
          <p className="ink-muted">{t("taking.loading")}</p>
        )}
        {error && (
          <Link to="/admin/exams" className="body-sm">
            ← {t("adminExamList.title")}
          </Link>
        )}
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div className="page">
        <p className="body" style={{ marginBottom: "var(--space-4)" }}>
          {t("preview.empty")}
        </p>
        <Button variant="secondary" onClick={() => navigate(back)}>
          ← {t("preview.back")}
        </Button>
      </div>
    );
  }

  const blank = groupQuestions(sections, questions)
    .map((g) => ({
      name: g.section?.subject_name ?? "",
      blank: g.questions.filter((q) => !isAnswered(q, answers, textAnswers)).length,
    }))
    .filter((g) => g.blank > 0);
  const blankTotal = blank.reduce((n, g) => n + g.blank, 0);
  const totalPoints = questions.reduce((n, q) => n + q.points, 0);

  return (
    <>
      <ExamScreen
        title={exam.title}
        sections={sections}
        questions={questions}
        answers={answers}
        textAnswers={textAnswers}
        remainingSeconds={remaining}
        onSelectOption={(questionId, optionId) => setAnswers((prev) => ({ ...prev, [questionId]: optionId }))}
        onChangeText={(questionId, text) => setTextAnswers((prev) => ({ ...prev, [questionId]: text }))}
        onSubmitClick={() => setSubmitOpen(true)}
        headerExtra={
          <Button variant="secondary" size="sm" onClick={() => navigate(back)}>
            ← {t("preview.back")}
          </Button>
        }
        notices={
          <div role="status" className="sp-review-bar sp-review-bar--stack" style={{ borderColor: "var(--info)" }}>
            <strong className="body-sm">{t("preview.bannerTitle")}</strong>
            <span className="body-sm ink-muted">
              {t("preview.bannerText", {
                questions: questions.length,
                points: formatPoints(totalPoints),
                minutes: exam.duration_minutes,
              })}
              {(exam.exam_type === "chorak" || exam.question_count > 1) && ` ${t("preview.shuffleNote")}`}
            </span>
          </div>
        }
      />

      <Modal open={submitOpen} onClose={() => setSubmitOpen(false)} title={t("taking.confirmTitle")}>
        <div className="stack">
          {blankTotal > 0 ? (
            <>
              <p className="body" style={{ color: "var(--warning)", fontWeight: 600 }}>
                {t("taking.confirmBlank", { count: blankTotal, total: questions.length })}
              </p>
              {sections.length > 0 && (
                <ul className="sp-intro-rules body-sm">
                  {blank.map((g) => (
                    <li key={g.name}>
                      {g.name}: {t("taking.confirmBlankInBlock", { count: g.blank })}
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="body">{t("taking.confirmAllAnswered", { total: questions.length })}</p>
          )}
          <p className="body-sm" style={{ color: "var(--info)" }}>
            {t("preview.submitNote")}
          </p>
          <div className="sp-exam__confirm-actions">
            <Button variant="secondary" onClick={() => setSubmitOpen(false)}>
              {t("preview.keepLooking")}
            </Button>
            <Button onClick={() => navigate(back)}>{t("preview.back")}</Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
