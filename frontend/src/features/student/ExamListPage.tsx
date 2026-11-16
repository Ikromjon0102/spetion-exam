import { enterFullscreen } from "../../hooks/useExamGuard";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listMyExams, type ExamListItem } from "../../api/studentApi";
import { AppHeader, Badge, Button, ListRow, type BadgeStatus, type RowState } from "../../components/ui";
import { formatDateShortUz, formatDateTimeUz, formatTimeUz } from "../../utils/formatDate";
import { useLanguage } from "../../i18n/LanguageContext";

const REFRESH_EVERY_MS = 60_000;

function finished(exam: ExamListItem): boolean {
  return exam.my_attempt_status === "submitted" || exam.my_attempt_status === "auto_submitted";
}

function inProgress(exam: ExamListItem): boolean {
  return exam.my_attempt_status === "in_progress" && exam.window_state === "active";
}

// Only an exam the student can act on right now is highlighted. An upcoming
// one used to get the brand-red border, which read as an error.
function rowState(exam: ExamListItem): RowState {
  return !finished(exam) && exam.window_state === "active" ? "now" : "resting";
}

function statusKey(exam: ExamListItem): { status: BadgeStatus; key: string } {
  if (finished(exam)) return { status: "success", key: "status.submitted" };
  if (inProgress(exam)) return { status: "warning", key: "status.resume" };
  if (exam.window_state === "active") return { status: "warning", key: "status.active" };
  if (exam.window_state === "upcoming") return { status: "info", key: "status.upcoming" };
  return { status: "neutral", key: "status.missed" };
}

export default function ExamListPage() {
  const [exams, setExams] = useState<ExamListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [includeOld, setIncludeOld] = useState(false);
  const { t } = useLanguage();
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    function load() {
      listMyExams(includeOld)
        .then((rows) => {
          if (cancelled) return;
          setExams(rows);
          setError(null);
        })
        .catch(() => {
          if (!cancelled) setError(t("examList.loadError"));
        });
    }
    load();
    // An exam that opens while the list is on screen shows up by itself — a
    // student waiting for 9:00 shouldn't have to know to reload the page.
    const interval = setInterval(load, REFRESH_EVERY_MS);
    const onVisible = () => document.visibilityState === "visible" && load();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeOld]);

  function openExam(exam: ExamListItem) {
    if (finished(exam)) {
      navigate(`/student/exams/${exam.id}/result`);
      return;
    }
    if (inProgress(exam)) {
      // Resuming: full-screen must be requested inside this click (a browser
      // rule) and survives the in-app navigation. A fresh start asks for it
      // from the intro screen's own "Boshlash" button instead.
      void enterFullscreen();
    }
    navigate(`/student/exams/${exam.id}`);
  }

  function subtitle(exam: ExamListItem): string {
    const parts = [
      exam.exam_type === "chorak" ? t("examType.chorakShort") : exam.subject_name,
      `${exam.duration_minutes} ${t("examList.minutes")}`,
    ];
    if (exam.question_count > 0) parts.push(`${exam.question_count} ${t("blocks.questionsShort")}`);
    if (!finished(exam)) {
      if (exam.window_state === "upcoming" && exam.start_at) {
        parts.push(`${t("examList.opensAt")} ${formatDateTimeUz(exam.start_at)}`);
      } else if (inProgress(exam) && exam.my_deadline_at) {
        parts.push(`${t("examList.untilTime")} ${formatTimeUz(exam.my_deadline_at)}`);
      } else if (exam.window_state === "active" && exam.end_at) {
        parts.push(`${t("examList.openUntil")} ${formatDateTimeUz(exam.end_at)}`);
      }
    }
    return parts.join(" · ");
  }

  return (
    <>
      <AppHeader />
      <div className="page">
        <h1 className="h2" style={{ marginBottom: "var(--space-6)" }}>
          {t("examList.title")}
        </h1>
        {error && (
          <p role="alert" style={{ color: "var(--danger)", marginBottom: "var(--space-4)" }}>
            {error}
          </p>
        )}
        {exams === null && !error && <p className="ink-muted">{t("taking.loading")}</p>}
        {exams !== null && exams.length === 0 && (
          <ListRow state="free" title={t("examList.empty")} subtitle={t("examList.emptySubtitle")} />
        )}
        <div className="row-stack">
          {(exams ?? []).map((exam) => {
            const badge = statusKey(exam);
            // An upcoming exam opens its info page too: what, when, how long.
            const clickable = finished(exam) || exam.window_state !== "closed";
            return (
              <ListRow
                key={exam.id}
                state={rowState(exam)}
                onClick={clickable ? () => openExam(exam) : undefined}
                chevron={clickable}
                leading={
                  <>
                    <span className="data-value">{exam.start_at ? formatTimeUz(exam.start_at) : "--:--"}</span>
                    <span className="data-sub">{exam.start_at ? formatDateShortUz(exam.start_at) : ""}</span>
                  </>
                }
                title={exam.title}
                subtitle={subtitle(exam)}
                trailing={<Badge status={badge.status}>{t(badge.key)}</Badge>}
              />
            );
          })}
        </div>
        <div style={{ marginTop: "var(--space-5)", textAlign: "center" }}>
          <Button variant="ghost" size="sm" onClick={() => setIncludeOld((v) => !v)}>
            {includeOld ? t("examList.hideOlder") : t("examList.showOlder")}
          </Button>
        </div>
      </div>
    </>
  );
}
