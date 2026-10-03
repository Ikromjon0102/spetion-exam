import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import {
  getDashboard,
  listExams,
  listMyAssignments,
  type DashboardData,
  type ExamPhase,
  type ExamSummary,
  type TeacherAssignment,
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

const PHASE_KEY: Record<ExamPhase, { status: BadgeStatus; key: string }> = {
  draft: { status: "neutral", key: "phase.draft" },
  upcoming: { status: "info", key: "phase.upcoming" },
  live: { status: "warning", key: "phase.live" },
  finished: { status: "success", key: "phase.finished" },
};

export default function DashboardPage() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";

  const [exams, setExams] = useState<ExamSummary[]>([]);
  // Everything else on this page — the school-wide counts, the per-class
  // bar chart and the live-exam progress (which "live" exams are open right
  // now is decided server-side from their time windows; see
  // routers/dashboard.py) — comes from ONE aggregate call, fetched in
  // parallel with the exam list. It used to download every class, subject,
  // student and teacher, then fetch each live exam's roster in a second wave.
  const [summary, setSummary] = useState<DashboardData | null>(null);
  const [assignments, setAssignments] = useState<TeacherAssignment[]>([]);
  const [loaded, setLoaded] = useState(false);

  const loadAll = useCallback(() => {
    const tasks: Promise<unknown>[] = [
      listExams().then(setExams).catch(() => undefined),
      getDashboard().then(setSummary).catch(() => undefined),
    ];
    if (!isAdmin) tasks.push(listMyAssignments().then(setAssignments).catch(() => undefined));
    Promise.allSettled(tasks).then(() => setLoaded(true));
  }, [isAdmin]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const liveProgress = summary?.live ?? [];
  const liveLoaded = loaded;

  function handleRefresh() {
    loadAll();
  }

  // By phase (derived from each exam's time window), not Exam.status: status
  // stays "scheduled" for ever, so last week's finished exams were being
  // counted — and listed below — as still upcoming.
  const phaseCounts: Record<string, number> = {};
  for (const e of exams) phaseCounts[e.phase] = (phaseCounts[e.phase] ?? 0) + 1;

  const needsAttention = exams.filter((e) => e.needs_review_count > 0).slice(0, 6);
  const upcomingOrActive = exams
    .filter((e) => e.phase === "live" || e.phase === "upcoming")
    .sort((a, b) => (a.start_at ?? "").localeCompare(b.start_at ?? ""))
    .slice(0, 6);

  const statusSegments = [
    { label: t("phase.draft"), value: phaseCounts.draft ?? 0, color: "var(--ink-faint)" },
    { label: t("phase.upcoming"), value: phaseCounts.upcoming ?? 0, color: "var(--info)" },
    { label: t("phase.live"), value: phaseCounts.live ?? 0, color: "var(--brand-600)" },
    { label: t("phase.finished"), value: phaseCounts.finished ?? 0, color: "var(--success)" },
  ].filter((s) => s.value > 0);

  const studentsPerClass = (summary?.students_per_class ?? [])
    .slice(0, 10)
    .map((c) => ({ label: c.class_name, value: c.count }));

  const liveTotals = liveProgress.reduce(
    (acc, p) => ({
      total: acc.total + p.total,
      submitted: acc.submitted + p.submitted,
      inProgress: acc.inProgress + p.in_progress,
      notStarted: acc.notStarted + p.not_started,
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
                {liveProgress.map(({ exam_id, title, subject_name, class_name, total, submitted, in_progress: inProgress }) => (
                  <ListRow
                    key={exam_id}
                    chevron
                    onClick={() => navigate(`/admin/exams/${exam_id}/ranking`)}
                    title={title}
                    subtitle={`${subject_name} · ${class_name}`}
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
              <StatCard label={t("dashboard.classes")} value={summary?.counts?.classes ?? 0} onClick={() => navigate("/classes")} />
              <StatCard
                label={t("dashboard.subjects")}
                value={summary?.counts?.subjects ?? 0}
                onClick={() => navigate("/admin/manage/subjects")}
              />
              <StatCard
                label={t("dashboard.students")}
                value={summary?.counts?.students ?? 0}
                onClick={() => navigate("/admin/manage/students")}
              />
              <StatCard
                label={t("dashboard.teachers")}
                value={summary?.counts?.teachers ?? 0}
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
                const badge = PHASE_KEY[exam.phase];
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
                    trailing={<Badge status={badge.status}>{t(badge.key)}</Badge>}
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
