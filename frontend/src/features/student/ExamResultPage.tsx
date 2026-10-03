import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getExamRanking, getResult, type ExamResult, type RankingEntry } from "../../api/studentApi";
import { AnswerOption, AppHeader, Card, ListRow, RankBadge } from "../../components/ui";
import RichText from "../../components/ui/RichText";
import { useLanguage } from "../../i18n/LanguageContext";
import { formatDateTimeUz } from "../../utils/formatDate";

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
            {result.score} / {result.max_score}
          </span>
          <span className="h4 ink-muted">({result.percent}%)</span>
        </div>

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
              </div>
              <div className="body" style={{ marginBottom: "var(--space-4)", fontWeight: 600 }}>
                <RichText block text={q.prompt_text} />
              </div>
              {q.question_type === "short_answer" ? (
                <div className="stack" style={{ gap: "var(--space-2)" }}>
                  <AnswerOption
                    letter={q.answer_text ? (q.is_correct ? "✓" : "✕") : "—"}
                    correct={!!q.answer_text && !!q.is_correct}
                    incorrect={!!q.answer_text && !q.is_correct}
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
                  {result.answers_revealed && q.ai_feedback && (
                    <p className="body-sm ink-muted">{q.ai_feedback}</p>
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
                {q.points_awarded ?? 0} / {q.points} {t("result.points")}
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
                      {r.score} {t("result.points")}
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
