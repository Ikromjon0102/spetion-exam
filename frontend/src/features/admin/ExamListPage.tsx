import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { deleteExam, listExams, type ExamSummary } from "../../api/adminApi";
import { AdminLayout, Badge, Button, ConfirmButton, ListRow, Toast, type BadgeStatus } from "../../components/ui";
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

export default function AdminExamListPage() {
  const [exams, setExams] = useState<ExamSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { t } = useLanguage();
  const navigate = useNavigate();
  const location = useLocation();
  // One-shot confirmation handed over by the page that navigated here (e.g.
  // the editor after publishing) — read once, then cleared from history so
  // a refresh doesn't show it again.
  const [flash, setFlash] = useState<string | null>((location.state as { flash?: string } | null)?.flash ?? null);
  useEffect(() => {
    if (flash) window.history.replaceState({}, "");
  }, [flash]);
  const [searchParams, setSearchParams] = useSearchParams();

  const statusFilter = searchParams.get("status");
  const needsReviewFilter = searchParams.get("needsReview") === "1";

  useEffect(() => {
    listExams()
      .then(setExams)
      .catch(() => setError(t("adminExamList.loadError")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredExams = useMemo(() => {
    return exams.filter((e) => {
      if (statusFilter && e.status !== statusFilter) return false;
      if (needsReviewFilter && e.needs_review_count <= 0) return false;
      return true;
    });
  }, [exams, statusFilter, needsReviewFilter]);

  const hasFilter = !!statusFilter || needsReviewFilter;

  async function handleDelete(examId: number) {
    try {
      await deleteExam(examId);
      setExams((prev) => prev.filter((e) => e.id !== examId));
    } catch (err) {
      setError(errorDetail(err, t("adminExamList.deleteError")));
    }
  }

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

        {hasFilter && (
          <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-4)" }}>
            {needsReviewFilter
              ? t("adminExamList.filteredNeedsReview")
              : `${t("adminExamList.filteredStatus")}: ${
                  statusFilter && STATUS_KEY[statusFilter] ? t(STATUS_KEY[statusFilter].key) : statusFilter
                }`}{" "}
            ·{" "}
            <button
              type="button"
              className="body-sm"
              style={{ color: "var(--brand-600)", background: "none", border: "none", cursor: "pointer", padding: 0 }}
              onClick={() => setSearchParams({})}
            >
              {t("adminExamList.clearFilter")}
            </button>
          </p>
        )}

        {flash && <Toast kind="success" text={flash} autoDismissMs={4000} onClose={() => setFlash(null)} />}
        {error && <Toast kind="error" text={error} onClose={() => setError(null)} />}
        {!error && exams.length === 0 && (
          <ListRow state="free" title={t("adminExamList.empty")} subtitle={t("adminExamList.emptySubtitle")} />
        )}
        {!error && exams.length > 0 && filteredExams.length === 0 && (
          <ListRow state="free" title={t("common.noSearchResults")} />
        )}

        <div className="row-stack">
          {filteredExams.map((exam) => {
            const badge: { status: BadgeStatus; key: string | null } = STATUS_KEY[exam.status] ?? {
              status: "neutral",
              key: null,
            };
            return (
              // Row itself isn't clickable (a chevron-navigate ListRow
              // renders as a <button>, and trailing now holds real buttons
              // too — the same nested-button conflict already fixed once
              // on Students/Teachers pages) — an explicit "Ko'rish" button
              // replaces the old whole-row click.
              <ListRow
                key={exam.id}
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
                    <Button variant="ghost" size="sm" onClick={() => navigate(`/admin/exams/${exam.id}/review`)}>
                      {t("adminExamList.view")}
                    </Button>
                    <ConfirmButton
                      label={t("common.delete")}
                      confirmLabel={t("common.confirmDelete")}
                      onConfirm={() => handleDelete(exam.id)}
                    />
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
