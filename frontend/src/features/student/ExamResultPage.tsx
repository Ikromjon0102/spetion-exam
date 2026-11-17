import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getExamRanking, getResult, type ExamResult, type RankingEntry } from "../../api/studentApi";
import { AnswerOption, AppHeader, Card, ListRow, RankBadge } from "../../components/ui";
import RichText from "../../components/ui/RichText";
import { useLanguage } from "../../i18n/LanguageContext";
import { formatDateTimeUz } from "../../utils/formatDate";
import { formatPoints } from "../../utils/formatPoints";
import "./examtaking.css";

export default function ExamResultPage() {
  const { examId } = useParams();
  const id = Number(examId);
  const { t } = useLanguage();

  const [result, setResult] = useState<ExamResult | null>(null);
  const [ranking, setRanking] = useState<RankingEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getResult(id)
      .then(setResult)
      .catch(() => setError(t("result.notReady")));
    getExamRanking(id)
      .then(setRanking)
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (error) {
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
  if (!result) {
    return (
      <>
        <AppHeader />
        <div className="page">
          <p className="ink-muted">{t("taking.loading")}</p>
        </div>
      </>
    );
  }

  // Same red/amber/green thresholds as StudentPerformancePage.tsx's
  // percentTone — a score page and the subject-performance page disagreeing
  // on what counts as "good" (this used to be a flat 60% pass/fail cutoff)
  // sent contradictory signals for the same number.
  const sectionNames = new Map(result.sections.map((s) => [s.section_id, s.subject_name]));
  const scoreColor = result.percent < 50 ? "var(--danger)" : result.percent < 70 ? "var(--warning)" : "var(--success)";

  return (
    <>
      <AppHeader />
      <div className="page">
        <p className="data-eyebrow" style={{ marginBottom: "var(--space-2)" }}>
          {result.exam_title}
        </p>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: "var(--space-3)",
            marginBottom: "var(--space-8)",
          }}
        >
          <span
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: 40,
              lineHeight: "44px",
              fontWeight: 800,
              color: scoreColor,
            }}
          >
            {formatPoints(result.score)} / {formatPoints(result.max_score)}
          </span>
          <span className="h4 ink-muted">({formatPoints(result.percent)}%)</span>
        </div>

        {result.sections.length > 0 && (
          <Card style={{ marginBottom: "var(--space-8)" }}>
            <h2 className="h4" style={{ marginBottom: "var(--space-3)" }}>
              {t("result.byBlock")}
            </h2>
            <table className="sp-block-table">
              <thead>
                <tr>
                  <th>{t("blocks.subject")}</th>
                  <th>{t("blocks.correct")}</th>
                  <th>{t("blocks.score")}</th>
                  <th>%</th>
                </tr>
              </thead>
              <tbody>
                {result.sections.map((s) => (
                  <tr key={s.section_id}>
                    <td>
                      {s.subject_name}
                      <span className="sp-block-table__kind">{t(`blocks.kind.${s.kind}`)}</span>
                    </td>
                    <td>
                      {s.correct_count}/{s.question_count}
                    </td>
                    <td>
                      {formatPoints(s.score)} / {formatPoints(s.max_score)}
                    </td>
                    <td>{s.max_score ? Math.round((100 * s.score) / s.max_score) : 0}%</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td>{t("blocks.total")}</td>
                  <td>
                    {result.sections.reduce((n, s) => n + s.correct_count, 0)}/
                    {result.sections.reduce((n, s) => n + s.question_count, 0)}
                  </td>
                  <td>
                    {formatPoints(result.score)} / {formatPoints(result.max_score)}
                  </td>
                  <td>{Math.round(result.percent)}%</td>
                </tr>
              </tfoot>
            </table>
          </Card>
        )}

        {result.questions.some((q) => q.pending_review) && (
          <p role="status" className="sp-review-bar body-sm" style={{ borderColor: "var(--info)" }}>
            {t("result.pendingReviewBanner", { count: result.questions.filter((q) => q.pending_review).length })}
          </p>
        )}

        <h2 className="h4" style={{ marginBottom: "var(--space-4)" }}>
          {t("result.byQuestion")}
        </h2>
        {!result.answers_revealed && (
          <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-4)" }}>
            {t("result.answersHiddenHint")}
            {result.reveal_at ? ` (${formatDateTimeUz(result.reveal_at)})` : ""}
          </p>
        )}
        <div className="stack" style={{ marginBottom: "var(--space-8)" }}>
          {result.questions.map((q, idx) => (
            <Card key={q.question_id}>
              <div className="data-eyebrow" style={{ marginBottom: "var(--space-2)" }}>
                {t("result.question")} {idx + 1}
                {q.section_id !== null && sectionNames.get(q.section_id) ? ` · ${sectionNames.get(q.section_id)}` : ""}
              </div>
              <div className="body" style={{ marginBottom: "var(--space-4)", fontWeight: 600 }}>
                <RichText block text={q.prompt_text} />
              </div>
              {q.question_type === "short_answer" ? (
                <div className="stack" style={{ gap: "var(--space-2)" }}>
                  <AnswerOption
                    letter={q.pending_review ? "…" : q.answer_text ? (q.is_correct ? "✓" : "✕") : "—"}
                    correct={!q.pending_review && !!q.answer_text && !!q.is_correct}
                    incorrect={!q.pending_review && !!q.answer_text && !q.is_correct}
                    disabled
                  >
                    {q.answer_text ? (
                      <>
                        <strong>{t("result.yourAnswer")}:</strong> {q.answer_text}
                      </>
                    ) : (
                      t("result.noAnswer")
                    )}
                  </AnswerOption>
                  {q.pending_review ? (
                    <p className="body-sm" style={{ color: "var(--info)" }}>
                      {t("result.pendingReview")}
                    </p>
                  ) : (
                    result.answers_revealed && q.ai_feedback && <p className="body-sm ink-muted">{q.ai_feedback}</p>
                  )}
                </div>
              ) : (
                <div className="stack" style={{ gap: "var(--space-2)" }}>
                  {/* We only have the student's selected + correct option ids/text, not the
                      full option list here — render those two, not a full option set.
                      While the exam window is still open (!answers_revealed), the backend
                      withholds the text entirely — don't reveal it via a bubble that names
                      "correct", and don't show the picked option's text either (a correct
                      pick would otherwise reveal the answer just as directly). */}
                  {result.answers_revealed && q.correct_option_id !== null && q.correct_option_id !== q.selected_option_id && (
                    <AnswerOption letter="✓" correct disabled>
                      <strong>{t("result.correctAnswer")}:</strong> <RichText text={q.correct_option_text ?? ""} />
                    </AnswerOption>
                  )}
                  {q.selected_option_id !== null ? (
                    <AnswerOption letter={q.is_correct ? "✓" : "✕"} correct={!!q.is_correct} incorrect={!q.is_correct} disabled>
                      {result.answers_revealed ? (
                        <>
                          <strong>{q.is_correct ? t("result.yourAnswerCorrect") : t("result.yourAnswer")}:</strong>{" "}
                          <RichText text={q.selected_option_text ?? ""} />
                        </>
                      ) : q.is_correct ? (
                        t("result.answeredCorrectHidden")
                      ) : (
                        t("result.answeredIncorrectHidden")
                      )}
                    </AnswerOption>
                  ) : (
                    <AnswerOption letter="—" incorrect disabled>
                      {t("result.noAnswer")}
                    </AnswerOption>
                  )}
                </div>
              )}
              <p className="caption" style={{ marginTop: "var(--space-3)" }}>
                {formatPoints(q.points_awarded ?? 0)} / {formatPoints(q.points)} {t("result.points")}
              </p>
            </Card>
          ))}
        </div>

        {ranking.length > 0 && (
          <>
            <h2 className="h4" style={{ marginBottom: "var(--space-4)" }}>
              {t("result.classRanking")}
            </h2>
            <div className="row-stack" style={{ marginBottom: "var(--space-8)" }}>
              {ranking.map((r) => (
                <ListRow
                  key={r.student_id}
                  state={r.is_me ? "next" : "resting"}
                  leading={<RankBadge rank={r.rank_in_class} />}
                  title={r.full_name}
                  trailing={
                    <span className="data-value">
                      {formatPoints(r.score)} {t("result.points")}
                    </span>
                  }
                />
              ))}
            </div>
          </>
        )}

        <Link to="/student/exams" className="body-sm">
          ← {t("result.backToList")}
        </Link>
      </div>
    </>
  );
}
