/**
 * The most failure-sensitive frontend surface — see CLAUDE.md "Next steps"
 * and docs/spec.md sections 2-3.
 *
 * Never renders is_correct anywhere here — the backend doesn't send it
 * before submission either (see AttemptOption in api/studentApi.ts).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getMyAttempt, startExam, submitAnswer, submitExam, type AttemptState } from "../../api/studentApi";
import { useExamTimer } from "../../hooks/useExamTimer";
import { AnswerOption, AppHeader, Button, Card } from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";
import "../../components/ui/examtimer.css";

const FAR_FUTURE = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
const LETTERS = ["A", "B", "C", "D", "E", "F"];

export default function ExamTakingPage() {
  const { examId } = useParams();
  const id = Number(examId);
  const navigate = useNavigate();
  const { t } = useLanguage();

  const [attempt, setAttempt] = useState<AttemptState | null>(null);
  const [answers, setAnswers] = useState<Record<number, number | null>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittedRef = useRef(false);

  function applyState(state: AttemptState) {
    setAttempt(state);
    const initial: Record<number, number | null> = {};
    state.questions.forEach((q) => {
      initial[q.id] = q.selected_option_id;
    });
    setAnswers(initial);
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const state = await getMyAttempt(id);
        if (!cancelled) applyState(state);
      } catch {
        try {
          const state = await startExam(id);
          if (!cancelled) applyState(state);
        } catch {
          if (!cancelled) setError(t("taking.startError"));
        }
      }
    }
    load();

    async function onVisible() {
      if (document.visibilityState !== "visible") return;
      try {
        const state = await getMyAttempt(id);
        if (!cancelled) applyState(state);
      } catch {
        // ignore — attempt may already be submitted, nothing to resync
      }
    }
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleSubmit = useCallback(async () => {
    if (submittedRef.current || !attempt) return;
    submittedRef.current = true;
    setSubmitting(true);
    try {
      await submitExam(id);
    } finally {
      navigate(`/student/exams/${id}/result`);
    }
  }, [id, navigate, attempt]);

  const remainingMs = useExamTimer(attempt?.deadline_at ?? FAR_FUTURE, handleSubmit);

  async function selectOption(questionId: number, optionId: number) {
    setAnswers((prev) => ({ ...prev, [questionId]: optionId }));
    try {
      await submitAnswer(id, questionId, { selected_option_id: optionId });
    } catch {
      setError(t("taking.answerSaveError"));
    }
  }

  if (error && !attempt) {
    return (
      <>
        <AppHeader />
        <div className="page">
          <p role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </p>
        </div>
      </>
    );
  }
  if (!attempt) {
    return (
      <>
        <AppHeader />
        <div className="page">
          <p className="ink-muted">{t("taking.loading")}</p>
        </div>
      </>
    );
  }

  const remainingSeconds = Math.max(0, Math.floor(remainingMs / 1000));
  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;
  const timerClass = remainingSeconds <= 30 ? "sp-timer--danger" : remainingSeconds <= 120 ? "sp-timer--warning" : "";
  const answeredCount = Object.values(answers).filter((v) => v !== null && v !== undefined).length;

  return (
    <>
      <AppHeader />
      <div className="page">
        <h1 className="h3" style={{ marginBottom: "var(--space-4)" }}>
          {attempt.exam_title}
        </h1>

        <div className={`sp-timer ${timerClass}`}>
          <div>
            <div className="data-eyebrow">{t("taking.timeLeft")}</div>
            <div className="sp-timer__value">
              {minutes}:{seconds.toString().padStart(2, "0")}
            </div>
          </div>
          <div className="caption">
            {answeredCount} / {attempt.questions.length} {t("taking.answeredOf")}
          </div>
        </div>

        {error && (
          <p role="alert" style={{ color: "var(--danger)", marginBottom: "var(--space-4)" }}>
            {error}
          </p>
        )}

        <div className="stack">
          {attempt.questions.map((q, idx) => (
            <Card key={q.id}>
              <div className="data-eyebrow" style={{ marginBottom: "var(--space-2)" }}>
                {t("taking.question")} {idx + 1} / {attempt.questions.length}
              </div>
              <p className="body-lg" style={{ marginBottom: "var(--space-4)" }}>
                {q.prompt_text}
              </p>
              <div className="stack" style={{ gap: "var(--space-2)" }}>
                {q.options.map((opt, optIdx) => (
                  <AnswerOption
                    key={opt.id}
                    letter={LETTERS[optIdx] ?? String(optIdx + 1)}
                    selected={answers[q.id] === opt.id}
                    disabled={submitting}
                    onClick={() => selectOption(q.id, opt.id)}
                  >
                    {opt.option_text}
                  </AnswerOption>
                ))}
              </div>
            </Card>
          ))}
        </div>

        <div style={{ marginTop: "var(--space-8)" }}>
          <Button size="lg" block onClick={handleSubmit} disabled={submitting}>
            {submitting ? t("taking.submitting") : t("taking.submit")}
          </Button>
        </div>
      </div>
    </>
  );
}
