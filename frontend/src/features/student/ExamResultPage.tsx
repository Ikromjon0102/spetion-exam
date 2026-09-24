import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getExamRanking, getResult, type ExamResult, type RankingEntry } from "../../api/studentApi";
import { AnswerOption, AppHeader, Card, ListRow } from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";

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

  const passed = result.percent >= 60;

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
              color: passed ? "var(--success)" : "var(--danger)",
            }}
          >
            {result.score} / {result.max_score}
          </span>
          <span className="h4 ink-muted">({result.percent}%)</span>
        </div>

        <h2 className="h4" style={{ marginBottom: "var(--space-4)" }}>
          {t("result.byQuestion")}
        </h2>
        <div className="stack" style={{ marginBottom: "var(--space-8)" }}>
          {result.questions.map((q, idx) => (
            <Card key={q.question_id}>
              <div className="data-eyebrow" style={{ marginBottom: "var(--space-2)" }}>
                {t("result.question")} {idx + 1}
              </div>
              <p className="body" style={{ marginBottom: "var(--space-4)", fontWeight: 600 }}>
                {q.prompt_text}
              </p>
              <div className="stack" style={{ gap: "var(--space-2)" }}>
                {/* We only have the student's selected + correct option ids, not the
                    full option list here — render those two, not a full option set. */}
                {q.correct_option_id !== null && q.correct_option_id !== q.selected_option_id && (
                  <AnswerOption letter="✓" correct disabled>
                    {t("result.correctAnswer")}
                  </AnswerOption>
                )}
                {q.selected_option_id !== null ? (
                  <AnswerOption letter={q.is_correct ? "✓" : "✕"} correct={!!q.is_correct} incorrect={!q.is_correct} disabled>
                    {q.is_correct ? t("result.yourAnswerCorrect") : t("result.yourAnswer")}
                  </AnswerOption>
                ) : (
                  <AnswerOption letter="—" incorrect disabled>
                    {t("result.noAnswer")}
                  </AnswerOption>
                )}
              </div>
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
                  leading={<span className="data-value">#{r.rank_in_class}</span>}
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
