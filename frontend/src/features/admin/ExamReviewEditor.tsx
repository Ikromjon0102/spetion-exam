import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  addQuestion,
  deleteQuestion,
  getExamDetail,
  publishExam,
  updateExam,
  updateQuestion,
  updateQuestionOption,
  type ExamDetail,
} from "../../api/adminApi";
import { AdminLayout, Badge, Button, Card, CardFoot, CardHead, type BadgeStatus } from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";
import { errorDetail } from "../../utils/errorDetail";

const STATUS_KEY: Record<string, { status: BadgeStatus; key: string }> = {
  draft: { status: "neutral", key: "status.draft" },
  review: { status: "warning", key: "status.review" },
  scheduled: { status: "info", key: "status.scheduled" },
  active: { status: "warning", key: "status.active" },
  closed: { status: "success", key: "status.closed" },
  archived: { status: "neutral", key: "status.archived" },
};

function toLocalInputValue(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function ExamReviewEditor() {
  const { examId } = useParams();
  const id = Number(examId);
  const { t } = useLanguage();
  const [exam, setExam] = useState<ExamDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [newQuestion, setNewQuestion] = useState({ prompt_text: "", options: ["", "", "", ""], correctIndex: 0 });

  async function reload() {
    try {
      setExam(await getExamDetail(id));
    } catch {
      setError(t("review.loadError"));
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (error && !exam) {
    return (
      <AdminLayout>
        <div className="page">
          <p role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </p>
        </div>
      </AdminLayout>
    );
  }
  if (!exam) {
    return (
      <AdminLayout>
        <div className="page">
          <p className="ink-muted">{t("taking.loading")}</p>
        </div>
      </AdminLayout>
    );
  }

  // Editable right up until a student actually starts the exam — a
  // published (scheduled/active) exam is still fair game as long as
  // exam.can_edit says nobody's begun it yet (see exam_service.ensure_no_attempts).
  const locked = !exam.can_edit;
  const canPublish = exam.status === "draft" || exam.status === "review";

  async function saveSchedule(patch: Partial<{ duration_minutes: number; start_at: string; end_at: string }>) {
    try {
      await updateExam(id, patch);
      await reload();
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  async function saveQuestion(
    questionId: number,
    patch: Partial<{ prompt_text: string; points: number; needs_review: boolean }>
  ) {
    try {
      await updateQuestion(id, questionId, patch);
      await reload();
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  async function setCorrectOption(questionId: number, optionId: number) {
    const question = exam?.questions.find((q) => q.id === questionId);
    const previous = question?.options.find((o) => o.is_correct && o.id !== optionId);
    try {
      if (previous) await updateQuestionOption(id, questionId, previous.id, { is_correct: false });
      await updateQuestionOption(id, questionId, optionId, { is_correct: true });
      await reload();
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  async function saveOptionText(questionId: number, optionId: number, text: string) {
    try {
      await updateQuestionOption(id, questionId, optionId, { option_text: text });
      await reload();
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  async function removeQuestion(questionId: number) {
    try {
      await deleteQuestion(id, questionId);
      await reload();
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  async function handleAddQuestion(e: React.FormEvent) {
    e.preventDefault();
    try {
      await addQuestion(id, {
        prompt_text: newQuestion.prompt_text,
        options: newQuestion.options.map((text, i) => ({ option_text: text, is_correct: i === newQuestion.correctIndex })),
      });
      setNewQuestion({ prompt_text: "", options: ["", "", "", ""], correctIndex: 0 });
      await reload();
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  async function handlePublish() {
    setMessage(null);
    setError(null);
    try {
      await publishExam(id);
      setMessage(t("review.published"));
      await reload();
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  const statusBadge = STATUS_KEY[exam.status];

  return (
    <AdminLayout>
      <div className="page">
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", marginBottom: "var(--space-1)" }}>
          <h1 className="h2">{exam.title}</h1>
          <Badge status={statusBadge?.status ?? "neutral"}>{statusBadge ? t(statusBadge.key) : exam.status}</Badge>
        </div>
        <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-6)" }}>
          {exam.subject_name} · {exam.class_name}
        </p>

        {error && (
          <p role="alert" className="body-sm" style={{ color: "var(--danger)", marginBottom: "var(--space-4)" }}>
            {error}
          </p>
        )}
        {message && (
          <p className="body-sm" style={{ color: "var(--success)", marginBottom: "var(--space-4)" }}>
            {message}
          </p>
        )}
        {locked && (
          <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-4)" }}>
            {t("review.lockedHint")}
          </p>
        )}

        <Card className="stack" style={{ marginBottom: "var(--space-8)" }}>
          <h2 className="h4">{t("review.schedule")}</h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-4)" }}>
            <div className="sp-field">
              <label className="sp-field__label">{t("review.duration")}</label>
              <input
                className="sp-input"
                type="number"
                defaultValue={exam.duration_minutes}
                disabled={locked}
                onBlur={(e) => saveSchedule({ duration_minutes: Number(e.target.value) })}
              />
            </div>
            <div className="sp-field">
              <label className="sp-field__label">{t("review.startAt")}</label>
              <input
                className="sp-input"
                type="datetime-local"
                defaultValue={toLocalInputValue(exam.start_at)}
                disabled={locked}
                onBlur={(e) => e.target.value && saveSchedule({ start_at: new Date(e.target.value).toISOString() })}
              />
            </div>
            <div className="sp-field">
              <label className="sp-field__label">{t("review.endAt")}</label>
              <input
                className="sp-input"
                type="datetime-local"
                defaultValue={toLocalInputValue(exam.end_at)}
                disabled={locked}
                onBlur={(e) => e.target.value && saveSchedule({ end_at: new Date(e.target.value).toISOString() })}
              />
            </div>
          </div>
        </Card>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-4)" }}>
          <h2 className="h3">{t("review.questions")}</h2>
          <span className="body-sm ink-muted">
            {exam.question_count} {t("review.questionsCount")} · {exam.needs_review_count} {t("review.needsReviewCount")}
          </span>
        </div>

        <div className="stack" style={{ marginBottom: "var(--space-6)" }}>
          {exam.questions.map((q, idx) => (
            <Card key={q.id}>
              <CardHead>
                <span className="data-eyebrow">
                  {t("review.question")} {idx + 1}
                </span>
                {q.needs_review && <Badge status="warning">{t("review.needsReviewBadge")}</Badge>}
                {q.parse_confidence === "low" && (
                  <Badge status="danger">{t("review.lowConfidenceBadge")}</Badge>
                )}
              </CardHead>
              <textarea
                className="sp-input"
                defaultValue={q.prompt_text}
                disabled={locked}
                rows={2}
                style={{ marginBottom: "var(--space-4)", resize: "vertical" }}
                onBlur={(e) => saveQuestion(q.id, { prompt_text: e.target.value })}
              />
              <div className="stack" style={{ gap: "var(--space-2)" }}>
                {q.options.map((opt) => (
                  <div key={opt.id} style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                    <input
                      type="radio"
                      name={`correct-${q.id}`}
                      checked={opt.is_correct}
                      disabled={locked}
                      onChange={() => setCorrectOption(q.id, opt.id)}
                      style={{ accentColor: "var(--brand-600)", width: 18, height: 18, flexShrink: 0 }}
                    />
                    <input
                      className="sp-input"
                      defaultValue={opt.option_text}
                      disabled={locked}
                      onBlur={(e) => saveOptionText(q.id, opt.id, e.target.value)}
                    />
                  </div>
                ))}
              </div>
              <CardFoot>
                <label className="body-sm" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                  <input
                    type="checkbox"
                    checked={q.needs_review}
                    disabled={locked}
                    onChange={(e) => saveQuestion(q.id, { needs_review: e.target.checked })}
                    style={{ accentColor: "var(--brand-600)" }}
                  />
                  {t("review.needsReviewCheckbox")}
                </label>
                <Button variant="ghost" size="sm" disabled={locked} onClick={() => removeQuestion(q.id)}>
                  {t("review.delete")}
                </Button>
              </CardFoot>
            </Card>
          ))}
        </div>

        {!locked && (
          <Card style={{ marginBottom: "var(--space-8)" }}>
            <h3 className="h4" style={{ marginBottom: "var(--space-4)" }}>
              {t("review.addQuestion")}
            </h3>
            <form onSubmit={handleAddQuestion} className="stack">
              <textarea
                className="sp-input"
                placeholder={t("review.promptPlaceholder")}
                value={newQuestion.prompt_text}
                onChange={(e) => setNewQuestion({ ...newQuestion, prompt_text: e.target.value })}
                rows={2}
                required
              />
              {newQuestion.options.map((text, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                  <input
                    type="radio"
                    name="new-correct"
                    checked={newQuestion.correctIndex === i}
                    onChange={() => setNewQuestion({ ...newQuestion, correctIndex: i })}
                    style={{ accentColor: "var(--brand-600)", width: 18, height: 18, flexShrink: 0 }}
                  />
                  <input
                    className="sp-input"
                    placeholder={`${t("review.optionPlaceholder")} ${String.fromCharCode(65 + i)}`}
                    value={text}
                    onChange={(e) => {
                      const options = [...newQuestion.options];
                      options[i] = e.target.value;
                      setNewQuestion({ ...newQuestion, options });
                    }}
                    required
                  />
                </div>
              ))}
              <Button type="submit" variant="secondary">
                {t("review.addQuestionSubmit")}
              </Button>
            </form>
          </Card>
        )}

        {canPublish ? (
          <Button size="lg" block onClick={handlePublish} disabled={locked || exam.needs_review_count > 0}>
            {t("review.publish")}
          </Button>
        ) : (
          <p className="body-sm ink-muted">{t("review.alreadyPublished")}</p>
        )}
      </div>
    </AdminLayout>
  );
}
