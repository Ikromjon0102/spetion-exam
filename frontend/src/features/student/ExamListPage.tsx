import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listMyExams, type ExamListItem } from "../../api/studentApi";
import { AppHeader, Badge, ListRow, type BadgeStatus, type RowState } from "../../components/ui";
import { formatDateShortUz, formatTimeUz } from "../../utils/formatDate";
import { useLanguage } from "../../i18n/LanguageContext";

function rowState(exam: ExamListItem): RowState {
  if (exam.my_attempt_status === "submitted" || exam.my_attempt_status === "auto_submitted") return "resting";
  if (exam.window_state === "active") return "now";
  if (exam.window_state === "upcoming") return "next";
  return "resting";
}

function statusKey(exam: ExamListItem): { status: BadgeStatus; key: string } {
  if (exam.my_attempt_status === "submitted" || exam.my_attempt_status === "auto_submitted") {
    return { status: "success", key: "status.submitted" };
  }
  if (exam.window_state === "active") return { status: "warning", key: "status.active" };
  if (exam.window_state === "upcoming") return { status: "info", key: "status.upcoming" };
  return { status: "neutral", key: "status.missed" };
}

function formatTime(iso: string | null): string {
  return iso ? formatTimeUz(iso) : "--:--";
}

function formatDate(iso: string | null): string {
  return iso ? formatDateShortUz(iso) : "";
}

export default function ExamListPage() {
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { t } = useLanguage();
  const navigate = useNavigate();

  useEffect(() => {
    listMyExams()
      .then(setExams)
      .catch(() => setError(t("examList.loadError")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function openExam(exam: ExamListItem) {
    if (exam.my_attempt_status === "submitted" || exam.my_attempt_status === "auto_submitted") {
      navigate(`/student/exams/${exam.id}/result`);
    } else if (exam.window_state === "active") {
      navigate(`/student/exams/${exam.id}`);
    }
  }

  return (
    <>
      <AppHeader />
      <div className="page">
        <h1 className="h2" style={{ marginBottom: "var(--space-6)" }}>
          {t("examList.title")}
        </h1>
        {error && (
          <p role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </p>
        )}
        {!error && exams.length === 0 && (
          <ListRow state="free" title={t("examList.empty")} subtitle={t("examList.emptySubtitle")} />
        )}
        <div className="row-stack">
          {exams.map((exam) => {
            const badge = statusKey(exam);
            const clickable =
              exam.window_state === "active" ||
              exam.my_attempt_status === "submitted" ||
              exam.my_attempt_status === "auto_submitted";
            return (
              <ListRow
                key={exam.id}
                state={rowState(exam)}
                onClick={clickable ? () => openExam(exam) : undefined}
                chevron={clickable}
                leading={
                  <>
                    <span className="data-value">{formatTime(exam.start_at)}</span>
                    <span className="data-sub">{formatDate(exam.start_at)}</span>
                  </>
                }
                title={exam.title}
                subtitle={`${exam.subject_name} · ${exam.duration_minutes} ${t("examList.minutes")}`}
                trailing={<Badge status={badge.status}>{t(badge.key)}</Badge>}
              />
            );
          })}
        </div>
      </div>
    </>
  );
}
