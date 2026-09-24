import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getClassRanking, listExamAttempts, type AttemptMonitor, type ClassRanking } from "../../api/adminApi";
import { AdminLayout, Badge, ListRow, StatCard, type BadgeStatus } from "../../components/ui";
import { formatDateTimeUz } from "../../utils/formatDate";
import { useLanguage } from "../../i18n/LanguageContext";

const STATUS_KEY: Record<string, { status: BadgeStatus; key: string }> = {
  not_started: { status: "neutral", key: "attemptStatus.not_started" },
  in_progress: { status: "warning", key: "attemptStatus.in_progress" },
  submitted: { status: "success", key: "attemptStatus.submitted" },
  auto_submitted: { status: "success", key: "attemptStatus.auto_submitted" },
  expired_unstarted: { status: "danger", key: "attemptStatus.expired_unstarted" },
};

export default function RankingPage() {
  const { examId } = useParams();
  const id = Number(examId);
  const [ranking, setRanking] = useState<ClassRanking | null>(null);
  const [attempts, setAttempts] = useState<AttemptMonitor[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { t } = useLanguage();

  useEffect(() => {
    getClassRanking(id)
      .then(setRanking)
      .catch(() => setError(t("ranking.loadError")));
    listExamAttempts(id)
      .then(setAttempts)
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  return (
    <AdminLayout>
      <div className="page">
        <h1 className="h2" style={{ marginBottom: "var(--space-6)" }}>
          {ranking?.exam_title ?? t("ranking.fallbackTitle")}
        </h1>
        {error && (
          <p role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </p>
        )}

        {attempts.length > 0 && (
          <div className="sp-statcard-grid" style={{ marginBottom: "var(--space-8)" }}>
            <StatCard label={t("ranking.totalStudents")} value={attempts.length} />
            <StatCard
              label={t("ranking.started")}
              value={attempts.filter((a) => a.status === "in_progress" || a.status === "submitted" || a.status === "auto_submitted").length}
              tone="warning"
            />
            <StatCard
              label={t("ranking.finished")}
              value={attempts.filter((a) => a.status === "submitted" || a.status === "auto_submitted").length}
              tone="success"
            />
            {attempts.some((a) => a.status === "expired_unstarted") && (
              <StatCard
                label={t("ranking.expired")}
                value={attempts.filter((a) => a.status === "expired_unstarted").length}
                tone="danger"
              />
            )}
          </div>
        )}

        {ranking && ranking.rankings.length > 0 && (
          <>
            <h2 className="h4" style={{ marginBottom: "var(--space-4)" }}>
              {t("ranking.title")}
            </h2>
            <div className="row-stack" style={{ marginBottom: "var(--space-8)" }}>
              {ranking.rankings.map((r) => (
                <ListRow
                  key={r.student_id}
                  leading={<span className="data-value">#{r.rank_in_class}</span>}
                  title={r.full_name}
                  trailing={
                    <span className="data-value">
                      {r.score} {t("result.points")}
                      {r.percentile !== null && ` · ${r.percentile}%`}
                    </span>
                  }
                />
              ))}
            </div>
          </>
        )}

        <h2 className="h4" style={{ marginBottom: "var(--space-4)" }}>
          {t("ranking.allStudents")}
        </h2>
        <div className="row-stack">
          {attempts.map((a) => {
            const badge: { status: BadgeStatus; key: string | null } = STATUS_KEY[a.status] ?? {
              status: "neutral",
              key: null,
            };
            return (
              <ListRow
                key={a.student_id}
                title={a.full_name}
                subtitle={
                  a.submitted_at
                    ? `${t("ranking.submittedAt")}: ${formatDateTimeUz(a.submitted_at)}`
                    : a.started_at
                    ? `${t("ranking.startedAt")}: ${formatDateTimeUz(a.started_at)}`
                    : undefined
                }
                trailing={
                  <>
                    {a.score !== null && (
                      <span className="data-value">
                        {a.score} {t("result.points")}
                      </span>
                    )}
                    <Badge status={badge.status}>{badge.key ? t(badge.key) : a.status}</Badge>
                  </>
                }
              />
            );
          })}
        </div>
      </div>
    </AdminLayout>
  );
}
