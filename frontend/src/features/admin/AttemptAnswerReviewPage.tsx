import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getAttemptAnswers,
  getExamDetail,
  listExamAttempts,
  overrideAttemptAnswer,
  type AttemptAnswerReview,
} from "../../api/adminApi";
import { AdminLayout, Badge, Button, Card, type BadgeStatus } from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";
import { errorDetail } from "../../utils/errorDetail";

export default function AttemptAnswerReviewPage() {
  const { examId, studentId } = useParams();
  const eid = Number(examId);
  const sid = Number(studentId);
  const { t } = useLanguage();

  const [answers, setAnswers] = useState<AttemptAnswerReview[] | null>(null);
  const [examTitle, setExamTitle] = useState("");
  const [studentName, setStudentName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState<Record<number, boolean>>({});

  async function reload() {
    try {
      const [rows, exam, attempts] = await Promise.all([
        getAttemptAnswers(eid, sid),
        getExamDetail(eid),
        listExamAttempts(eid),
      ]);
      setAnswers(rows);
      setExamTitle(exam.title);
      setStudentName(attempts.find((a) => a.student_id === sid)?.full_name ?? "");
    } catch (e) {
      setError(errorDetail(e, t("attemptReview.loadError")));
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eid, sid]);

  async function handleOverride(questionId: number, maxPoints: number) {
    const raw = drafts[questionId];
    const value = Number(raw);
    if (raw === undefined || raw === "" || Number.isNaN(value) || value < 0 || value > maxPoints) {
      setError(t("attemptReview.invalidPoints", { max: maxPoints }));
      return;
    }
    setError(null);
    setSaving((prev) => ({ ...prev, [questionId]: true }));
    try {
      await overrideAttemptAnswer(eid, sid, questionId, value);
      await reload();
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[questionId];
        return next;
      });
    } catch (e) {
      setError(errorDetail(e, t("attemptReview.saveError")));
    } finally {
      setSaving((prev) => ({ ...prev, [questionId]: false }));
    }
  }

  const GRADED_BY_BADGE: Record<string, { status: BadgeStatus; key: string }> = {
    ai: { status: "info", key: "attemptReview.gradedByAi" },
    teacher: { status: "success", key: "attemptReview.gradedByTeacher" },
  };

  return (
    <AdminLayout>
      <div className="page">
        <Link
          to={`/admin/exams/${eid}/ranking`}
          className="body-sm"
          style={{ display: "inline-block", marginBottom: "var(--space-3)" }}
        >
          &larr; {t("attemptReview.backToRanking")}
        </Link>
        <h1 className="h2" style={{ marginBottom: "var(--space-1)" }}>
          {studentName || t("attemptReview.title")}
        </h1>
        <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-6)" }}>
          {examTitle}
        </p>

        {error && (
          <p role="alert" className="body-sm" style={{ color: "var(--danger)", marginBottom: "var(--space-4)" }}>
            {error}
          </p>
        )}

        <div className="stack">
          {answers?.map((a, idx) => {
            const badge = a.graded_by ? GRADED_BY_BADGE[a.graded_by] : null;
            return (
              <Card key={a.question_id}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: "var(--space-3)",
                  }}
                >
                  <span className="data-eyebrow">
                    {t("attemptReview.question")} {idx + 1}
                  </span>
                  {badge && <Badge status={badge.status}>{t(badge.key)}</Badge>}
                </div>
                <p className="body" style={{ fontWeight: 600, marginBottom: "var(--space-3)" }}>
                  {a.prompt_text}
                </p>

                {a.question_type === "short_answer" ? (
                  <div className="stack" style={{ gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
                    <div>
                      <span className="data-eyebrow">{t("attemptReview.referenceAnswer")}</span>
                      <p className="body-sm ink-muted">{a.reference_answer || "—"}</p>
                    </div>
                    <div>
                      <span className="data-eyebrow">{t("attemptReview.studentAnswer")}</span>
                      <p className="body-sm">{a.answer_text || t("attemptReview.noAnswer")}</p>
                    </div>
                    {a.ai_feedback && (
                      <div>
                        <span className="data-eyebrow">{t("attemptReview.aiFeedback")}</span>
                        <p className="body-sm ink-muted">{a.ai_feedback}</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="body-sm" style={{ marginBottom: "var(--space-3)" }}>
                    <strong>{t("attemptReview.studentAnswer")}:</strong>{" "}
                    {a.selected_option_text || t("attemptReview.noAnswer")}
                  </p>
                )}

                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                  <Badge status={a.is_correct ? "success" : "danger"}>
                    {a.is_correct ? t("attemptReview.correct") : t("attemptReview.incorrect")}
                  </Badge>
                  {a.question_type === "short_answer" ? (
                    <>
                      <input
                        className="sp-input"
                        type="number"
                        min={0}
                        max={a.points}
                        step="0.5"
                        style={{ width: 90 }}
                        placeholder={String(a.points_awarded ?? 0)}
                        value={drafts[a.question_id] ?? ""}
                        onChange={(e) => setDrafts((prev) => ({ ...prev, [a.question_id]: e.target.value }))}
                      />
                      <span className="body-sm ink-muted">/ {a.points}</span>
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={saving[a.question_id] || drafts[a.question_id] === undefined}
                        onClick={() => handleOverride(a.question_id, a.points)}
                      >
                        {t("attemptReview.overrideSave")}
                      </Button>
                    </>
                  ) : (
                    <span className="data-value">
                      {a.points_awarded ?? 0} / {a.points}
                    </span>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      </div>
    </AdminLayout>
  );
}
