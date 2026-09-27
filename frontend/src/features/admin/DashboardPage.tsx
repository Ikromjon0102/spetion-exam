import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import {
  listAdminClasses,
  listAdminStudents,
  listAdminSubjects,
  listAdminTeachers,
  listExamAttempts,
  listExams,
  listMyAssignments,
  type ClassOut,
  type ExamSummary,
  type StudentRow,
  type SubjectOut,
  type TeacherAssignment,
  type TeacherRow,
} from "../../api/adminApi";
import {
  AdminLayout,
  Badge,
  BarChart,
  Button,
  Card,
  DonutChart,
  ListRow,
  StatCard,
  type BadgeStatus,
} from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";
import { formatDateTimeUz } from "../../utils/formatDate";

const STATUS_KEY: Record<string, { status: BadgeStatus; key: string }> = {
  draft: { status: "neutral", key: "status.draft" },
  review: { status: "warning", key: "status.review" },
  scheduled: { status: "info", key: "status.scheduled" },
  active: { status: "warning", key: "status.active" },
  closed: { status: "success", key: "status.closed" },
  archived: { status: "neutral", key: "status.archived" },
};

// Exam.status never actually transitions to "active" anywhere in the
// backend (publish_exam sets "scheduled" and it stays there for the
// exam's whole life, time window included) — so "is this exam happening
// right now" has to be computed from start_at/end_at, the same way
// routers/student.py's _window_state does, not read off the stored status.
function isLiveNow(exam: ExamSummary): boolean {
  if (exam.status !== "scheduled" && exam.status !== "active") return false;
  if (!exam.start_at || !exam.end_at) return false;
  const now = Date.now();
  return now >= new Date(exam.start_at).getTime() && now < new Date(exam.end_at).getTime();
}

interface LiveProgress {
  exam: ExamSummary;
  total: number;
  submitted: number;
  inProgress: number;
  notStarted: number;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";

  const [exams, setExams] = useState<ExamSummary[]>([]);
  const [classes, setClasses] = useState<ClassOut[]>([]);
  const [subjects, setSubjects] = useState<SubjectOut[]>([]);
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [teachers, setTeachers] = useState<TeacherRow[]>([]);
  const [assignments, setAssignments] = useState<TeacherAssignment[]>([]);
  const [loaded, setLoaded] = useState(false);

  const [liveProgress, setLiveProgress] = useState<LiveProgress[]>([]);
  const [liveLoaded, setLiveLoaded] = useState(false);

  const loadAll = useCallback(() => {
    const tasks: Promise<unknown>[] = [listExams().then(setExams).catch(() => undefined)];
    if (isAdmin) {
      tasks.push(listAdminClasses().then(setClasses).catch(() => undefined));
      tasks.push(listAdminSubjects().then(setSubjects).catch(() => undefined));
      tasks.push(listAdminStudents().then(setStudents).catch(() => undefined));
      tasks.push(listAdminTeachers().then(setTeachers).catch(() => undefined));
    } else {
      tasks.push(listMyAssignments().then(setAssignments).catch(() => undefined));
    }
    Promise.allSettled(tasks).then(() => setLoaded(true));
  }, [isAdmin]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const loadLive = useCallback((examList: ExamSummary[]) => {
    const live = examList.filter(isLiveNow);
    if (live.length === 0) {
      setLiveProgress([]);
      setLiveLoaded(true);
      return;
    }
    setLiveLoaded(false);
    Promise.all(
      live.map((exam) =>
        listExamAttempts(exam.id)
          .then(
            (attempts): LiveProgress => ({
              exam,
              total: attempts.length,
              submitted: attempts.filter((a) => a.status === "submitted" || a.status === "auto_submitted").length,
              inProgress: attempts.filter((a) => a.status === "in_progress").length,
              notStarted: attempts.filter((a) => a.status === "not_started").length,
            })
          )
          .catch(() => null)
      )
    ).then((results) => {
      setLiveProgress(results.filter((r): r is LiveProgress => r !== null));
      setLiveLoaded(true);
    });
  }, []);

  useEffect(() => {
    if (loaded) loadLive(exams);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded]);

  function handleRefresh() {
    loadAll();
    loadLive(exams);
  }

  const statusCounts: Record<string, number> = {};
  for (const e of exams) statusCounts[e.status] = (statusCounts[e.status] ?? 0) + 1;

  const needsAttention = exams.filter((e) => e.needs_review_count > 0).slice(0, 6);
  const upcomingOrActive = exams
    .filter((e) => e.status === "active" || e.status === "scheduled")
    .sort((a, b) => (a.start_at ?? "").localeCompare(b.start_at ?? ""))
    .slice(0, 6);

  const statusSegments = [
    { label: t("status.draft"), value: statusCounts.draft ?? 0, color: "var(--ink-faint)" },
    { label: t("status.review"), value: statusCounts.review ?? 0, color: "var(--warning)" },
    { label: t("status.scheduled"), value: statusCounts.scheduled ?? 0, color: "var(--info)" },
    { label: t("status.active"), value: statusCounts.active ?? 0, color: "var(--brand-600)" },
    { label: t("status.closed"), value: statusCounts.closed ?? 0, color: "var(--success)" },
  ].filter((s) => s.value > 0);

  const studentsPerClass = isAdmin
    ? classes
        .map((c) => ({
          label: c.display_name,
          value: students.filter((s) => s.class_id === c.id).length,
        }))
        .filter((c) => c.value > 0)
        .sort((a, b) => b.value - a.value)
        .slice(0, 10)
    : [];

  const liveTotals = liveProgress.reduce(
    (acc, p) => ({
      total: acc.total + p.total,
      submitted: acc.submitted + p.submitted,
      inProgress: acc.inProgress + p.inProgress,
      notStarted: acc.notStarted + p.notStarted,
    }),
    { total: 0, submitted: 0, inProgress: 0, notStarted: 0 }
  );

  return (
    <AdminLayout>
      <div className="page">
        <h1 className="h2" style={{ marginBottom: "var(--space-1)" }}>
          {t("dashboard.greeting")}, {user?.full_name}
        </h1>
        <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-8)" }}>
          {isAdmin ? t("dashboard.subtitleAdmin") : t("dashboard.subtitleTeacher")}
        </p>

        {/* Student-centric hero: what's actually happening with students
            right now, ahead of any administrative counts below. */}
        <Card
          style={{
            marginBottom: "var(--space-8)",
            borderColor: liveProgress.length > 0 ? "var(--brand-600)" : undefined,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "var(--space-5)",
              gap: "var(--space-3)",
              flexWrap: "wrap",
            }}
          >
            <h2 className="h3" style={{ margin: 0, display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              {liveProgress.length > 0 && <span className="sp-live-dot" />}
              {t("dashboard.liveNow")}
            </h2>
            <Button variant="ghost" size="sm" onClick={handleRefresh}>
              {t("dashboard.refresh")}
            </Button>
          </div>

          {!liveLoaded ? (
            <p className="body-sm ink-muted">{t("taking.loading")}</p>
          ) : liveProgress.length === 0 ? (
            <p className="body-sm ink-muted">{t("dashboard.noLiveExams")}</p>
          ) : (
            <>
              <div className="sp-statcard-grid" style={{ marginBottom: "var(--space-5)" }}>
                <StatCard label={t("dashboard.liveExamsCount")} value={liveProgress.length} />
                <StatCard label={t("dashboard.liveInProgress")} value={liveTotals.inProgress} tone="warning" />
                <StatCard label={t("dashboard.liveSubmitted")} value={liveTotals.submitted} tone="success" />
                <StatCard label={t("dashboard.liveNotStarted")} value={liveTotals.notStarted} />
              </div>
              <div className="row-stack">
                {liveProgress.map(({ exam, total, submitted, inProgress }) => (
                  <ListRow
                    key={exam.id}
                    chevron
                    onClick={() => navigate(`/admin/exams/${exam.id}/ranking`)}
                    title={exam.title}
                    subtitle={`${exam.subject_name} · ${exam.class_name}`}
                    trailing={
                      <>
                        {inProgress > 0 && (
                          <Badge status="warning">
                            {inProgress} {t("dashboard.liveInProgress").toLowerCase()}
                          </Badge>
                        )}
                        <Badge status="success">
                          {submitted}/{total} {t("dashboard.liveSubmittedOf")}
                        </Badge>
                      </>
                    }
                  />
                ))}
              </div>
            </>
          )}
        </Card>

        <div className="sp-statcard-grid" style={{ marginBottom: "var(--space-8)" }}>
          {isAdmin ? (
            <>
              <StatCard label={t("dashboard.classes")} value={classes.length} onClick={() => navigate("/classes")} />
              <StatCard
                label={t("dashboard.subjects")}
                value={subjects.length}
                onClick={() => navigate("/admin/manage/subjects")}
              />
              <StatCard
                label={t("dashboard.students")}
                value={students.length}
                onClick={() => navigate("/admin/manage/students")}
              />
              <StatCard
                label={t("dashboard.teachers")}
                value={teachers.length}
                onClick={() => navigate("/admin/manage/teachers")}
              />
            </>
          ) : (
            <StatCard label={t("dashboard.myAssignments")} value={assignments.length} />
          )}
          <StatCard label={t("dashboard.myExams")} value={exams.length} onClick={() => navigate("/admin/exams")} />
          <StatCard
            label={t("dashboard.needsAttention")}
            value={exams.filter((e) => e.needs_review_count > 0).length}
            tone="danger"
            onClick={() => navigate("/admin/exams?needsReview=1")}
          />
        </div>

        <div style={{ display: "flex", gap: "var(--space-3)", marginBottom: "var(--space-8)" }}>
          <Button onClick={() => navigate("/admin/exams/upload")}>{t("adminExamList.new")}</Button>
          <Button variant="secondary" onClick={() => navigate("/admin/exams")}>
            {t("dashboard.allExams")}
          </Button>
        </div>

        {loaded && statusSegments.length > 0 && (
          <Card style={{ marginBottom: "var(--space-6)" }}>
            <h2 className="h4" style={{ marginBottom: "var(--space-4)" }}>
              {t("dashboard.statusChartTitle")}
            </h2>
            <DonutChart segments={statusSegments} />
          </Card>
        )}

        {loaded && studentsPerClass.length > 0 && (
          <Card style={{ marginBottom: "var(--space-8)" }}>
            <h2 className="h4" style={{ marginBottom: "var(--space-4)" }}>
              {t("dashboard.classSizeChartTitle")}
            </h2>
            <BarChart data={studentsPerClass} />
          </Card>
        )}

        {loaded && needsAttention.length > 0 && (
          <>
            <h2 className="h4" style={{ marginBottom: "var(--space-4)" }}>
              {t("dashboard.needsAttentionTitle")}
            </h2>
            <div className="row-stack" style={{ marginBottom: "var(--space-8)" }}>
              {needsAttention.map((exam) => (
                <ListRow
                  key={exam.id}
                  chevron
                  onClick={() => navigate(`/admin/exams/${exam.id}/review`)}
                  title={exam.title}
                  subtitle={`${exam.subject_name} · ${exam.class_name}`}
                  trailing={
                    <Badge status="danger">
                      {exam.needs_review_count} {t("adminExamList.needsReview")}
                    </Badge>
                  }
                />
              ))}
            </div>
          </>
        )}

        {loaded && upcomingOrActive.length > 0 && (
          <>
            <h2 className="h4" style={{ marginBottom: "var(--space-4)" }}>
              {t("dashboard.upcomingTitle")}
            </h2>
            <div className="row-stack" style={{ marginBottom: "var(--space-8)" }}>
              {upcomingOrActive.map((exam) => {
                const badge = STATUS_KEY[exam.status] ?? { status: "neutral" as BadgeStatus, key: null };
                return (
                  <ListRow
                    key={exam.id}
                    chevron
                    onClick={() => navigate(`/admin/exams/${exam.id}/review`)}
                    title={exam.title}
                    subtitle={
                      exam.start_at
                        ? `${exam.subject_name} · ${exam.class_name} · ${formatDateTimeUz(exam.start_at)}`
                        : `${exam.subject_name} · ${exam.class_name}`
                    }
                    trailing={<Badge status={badge.status}>{badge.key ? t(badge.key) : exam.status}</Badge>}
                  />
                );
              })}
            </div>
          </>
        )}

        {loaded && needsAttention.length === 0 && upcomingOrActive.length === 0 && (
          <Card>
            <p className="body-sm ink-muted">{t("dashboard.allClear")}</p>
          </Card>
        )}
      </div>
    </AdminLayout>
  );
}
