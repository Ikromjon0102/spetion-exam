import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listExams, type ExamSummary } from "../../api/adminApi";
import { AdminLayout, Badge, Button, ListRow, type BadgeStatus } from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";

const STATUS_KEY: Record<string, { status: BadgeStatus; key: string }> = {
  draft: { status: "neutral", key: "status.draft" },
  review: { status: "warning", key: "status.review" },
  scheduled: { status: "info", key: "status.scheduled" },
  active: { status: "warning", key: "status.active" },
  closed: { status: "success", key: "status.closed" },
  archived: { status: "neutral", key: "status.archived" },
};

export default function AdminExamListPage() {
  const [exams, setExams] = useState<ExamSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { t } = useLanguage();
  const navigate = useNavigate();

  useEffect(() => {
    listExams()
      .then(setExams)
      .catch(() => setError(t("adminExamList.loadError")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AdminLayout>
      <div className="page">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "var(--space-6)",
          }}
        >
          <h1 className="h2">{t("adminExamList.title")}</h1>
          <Button size="sm" onClick={() => navigate("/admin/exams/upload")}>
            {t("adminExamList.new")}
          </Button>
        </div>

        {error && (
          <p role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </p>
        )}
        {!error && exams.length === 0 && (
          <ListRow state="free" title={t("adminExamList.empty")} subtitle={t("adminExamList.emptySubtitle")} />
        )}

        <div className="row-stack">
          {exams.map((exam) => {
            const badge: { status: BadgeStatus; key: string | null } = STATUS_KEY[exam.status] ?? {
              status: "neutral",
              key: null,
            };
            return (
              <ListRow
                key={exam.id}
                chevron
                onClick={() => navigate(`/admin/exams/${exam.id}/review`)}
                leading={
                  <>
                    <span className="data-eyebrow">{exam.class_name}</span>
                    <span className="data-value">{exam.question_count}</span>
                  </>
                }
                title={exam.title}
                subtitle={`${exam.subject_name} · ${exam.duration_minutes} ${t("examList.minutes")}`}
                trailing={
                  <>
                    {exam.needs_review_count > 0 && (
                      <Badge status="danger">
                        {exam.needs_review_count} {t("adminExamList.needsReview")}
                      </Badge>
                    )}
                    <Badge status={badge.status}>{badge.key ? t(badge.key) : exam.status}</Badge>
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
