import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  deleteAttempt,
  getClassRanking,
  getExamDetail,
  getQuestionStats,
  getSectionResults,
  listExamAttempts,
  type AttemptMonitor,
  type ClassRanking,
  type ExamDetail,
  type QuestionStats,
  type SectionResults,
} from "../../api/adminApi";
import { AdminLayout, Badge, Button, ConfirmButton, ListRow, RankBadge, StatCard, type BadgeStatus } from "../../components/ui";
import { formatDateTimeUz } from "../../utils/formatDate";
import { formatPoints } from "../../utils/formatPoints";
import { useLanguage } from "../../i18n/LanguageContext";
import { useAuth } from "../../auth/AuthContext";
import RichText from "../../components/ui/RichText";

const STATUS_KEY: Record<string, { status: BadgeStatus; key: string }> = {
  not_started: { status: "neutral", key: "attemptStatus.not_started" },
  in_progress: { status: "warning", key: "attemptStatus.in_progress" },
  submitted: { status: "success", key: "attemptStatus.submitted" },
  auto_submitted: { status: "success", key: "attemptStatus.auto_submitted" },
  expired_unstarted: { status: "danger", key: "attemptStatus.expired_unstarted" },
};

const LIVE_REFRESH_MS = 20_000;

function isDone(status: string): boolean {
  return status === "submitted" || status === "auto_submitted";
}

/** Excel-friendly CSV: a BOM so Cyrillic/apostrophes survive, ";" because
 * that is the list separator of the ru/uz Windows locales the school uses. */
function downloadCsv(filename: string, rows: (string | number | null)[][]) {
  const escape = (value: string | number | null) => {
    const text = value === null ? "" : String(value);
    return /[";\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const csv = "﻿" + rows.map((row) => row.map(escape).join(";")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export default function RankingPage() {
  const { examId } = useParams();
  const id = Number(examId);
  const [exam, setExam] = useState<ExamDetail | null>(null);
  const [ranking, setRanking] = useState<ClassRanking | null>(null);
  const [attempts, setAttempts] = useState<AttemptMonitor[]>([]);
  const [blocks, setBlocks] = useState<SectionResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<QuestionStats | null>(null);
  // hardest first is what a teacher wants; paper order is there to look one up
  const [statsOrder, setStatsOrder] = useState<"hardest" | "paper">("hardest");
  const [openQuestionId, setOpenQuestionId] = useState<number | null>(null);
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  async function reload() {
    // A class's homeroom teacher may see a chorak exam's results without
    // being able to open the exam itself, so a failed detail isn't fatal.
    const detail = await getExamDetail(id).catch(() => null);
    setExam(detail);
    listExamAttempts(id)
      .then((rows) => {
        setAttempts(rows);
        setError(null);
      })
      .catch(() => setError(t("ranking.loadError")));
    getClassRanking(id)
      .then(setRanking)
      .catch(() => undefined);
    getQuestionStats(id)
      .then(setStats)
      .catch(() => setStats(null));
    if (detail === null || detail.exam_type === "chorak") {
      getSectionResults(id)
        .then(setBlocks)
        .catch(() => setBlocks(null));
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // While the exam is running this page is a live monitor: keep it current
  // without the teacher having to reload.
  const live = exam?.phase === "live";
  useEffect(() => {
    if (!live) return;
    const interval = setInterval(reload, LIVE_REFRESH_MS);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live, id]);

  async function handleDeleteAttempt(studentId: number) {
    try {
      await deleteAttempt(id, studentId);
      reload();
    } catch {
      setError(t("ranking.deleteAttemptError"));
    }
  }

  const title = exam?.title ?? blocks?.exam_title ?? ranking?.exam_title ?? t("ranking.fallbackTitle");
  const started = attempts.filter((a) => a.status === "in_progress" || isDone(a.status)).length;
  const finished = attempts.filter((a) => isDone(a.status)).length;
  const expired = attempts.filter((a) => a.status === "expired_unstarted").length;
  const hasResults = blocks ? blocks.students.some((s) => s.rank !== null) : (ranking?.rankings.length ?? 0) > 0;

  function exportCsv() {
    const name = `${title}.csv`;
    if (blocks) {
      const header = ["#", t("ranking.student"), ...blocks.sections.map((s) => `${s.subject_name} (${formatPoints(s.max_score)})`)];
      if (blocks.shows_total) header.push(`${t("blocks.total")} (${formatPoints(blocks.max_total)})`, "%");
      const rows = blocks.students.map((s) => {
        const row: (string | number | null)[] = [s.rank, s.full_name, ...s.scores.map((v) => (v === null ? null : formatPoints(v)))];
        if (blocks.shows_total) {
          row.push(
            s.total === null ? null : formatPoints(s.total),
            s.total === null || !blocks.max_total ? null : Math.round((100 * s.total) / blocks.max_total)
          );
        }
        return row;
      });
      downloadCsv(name, [header, ...rows]);
    } else if (ranking) {
      downloadCsv(name, [
        ["#", t("ranking.student"), t("blocks.score"), t("ranking.maxScore"), "%"],
        ...ranking.rankings.map((r) => [
          r.rank_in_class,
          r.full_name,
          formatPoints(r.score),
          formatPoints(r.max_score),
          r.max_score ? Math.round((100 * r.score) / r.max_score) : null,
        ]),
      ]);
    }
  }

  return (
    <AdminLayout>
      <div className="page">
        <Link to="/admin/exams" className="body-sm no-print" style={{ display: "inline-block", marginBottom: "var(--space-3)" }}>
          ← {t("adminExamList.title")}
        </Link>
        <div className="sp-page-head">
          <div>
            <h1 className="h2" style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap" }}>
              {live && <span className="sp-live-dot" />}
              {title}
            </h1>
            <p className="body-sm ink-muted">
              {exam ? (exam.exam_type === "chorak" ? exam.class_name : `${exam.subject_name} · ${exam.class_name}`) : blocks?.class_name}
              {live ? ` · ${t("ranking.liveHint")}` : ""}
            </p>
          </div>
          <div className="no-print" style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
            <Button variant="ghost" size="sm" onClick={reload}>
              {t("dashboard.refresh")}
            </Button>
            {hasResults && (
              <>
                <Button variant="secondary" size="sm" onClick={exportCsv}>
                  {t("ranking.exportExcel")}
                </Button>
                <Button variant="secondary" size="sm" onClick={() => window.print()}>
                  {t("common.print")}
                </Button>
              </>
            )}
            {exam && (
              <Button variant="ghost" size="sm" onClick={() => navigate(`/admin/exams/${id}/review`)}>
                {t("ranking.openExam")}
              </Button>
            )}
          </div>
        </div>
        {error && (
          <p role="alert" style={{ color: "var(--danger)", marginBottom: "var(--space-4)" }}>
            {error}
          </p>
        )}

        {attempts.length > 0 && (
          <div className="sp-statcard-grid" style={{ marginBottom: "var(--space-8)" }}>
            <StatCard label={t("ranking.totalStudents")} value={attempts.length} />
            <StatCard label={t("ranking.started")} value={started} tone="warning" />
            <StatCard label={t("ranking.finished")} value={finished} tone="success" />
            {expired > 0 && <StatCard label={t("ranking.expired")} value={expired} tone="danger" />}
          </div>
        )}

        {blocks ? (
          <>
            <h2 className="h4" style={{ marginBottom: "var(--space-2)" }}>
              {t("ranking.byBlocks")}
            </h2>
            {!blocks.shows_total && (
              <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-3)" }}>
                {t("ranking.ownBlocksOnly")}
              </p>
            )}
            <div className="sp-table-scroll" style={{ marginBottom: "var(--space-8)" }}>
              <table className="sp-data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th className="sp-data-table__text">{t("ranking.student")}</th>
                    {blocks.sections.map((s) => (
                      <th key={s.section_id}>
                        {s.subject_name}
                        <br />
                        {formatPoints(s.max_score)}
                      </th>
                    ))}
                    {blocks.shows_total && (
                      <>
                        <th>
                          {t("blocks.total")}
                          <br />
                          {formatPoints(blocks.max_total)}
                        </th>
                        <th>%</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {blocks.students.map((s) => (
                    <tr key={s.student_id}>
                      <td>{s.rank ?? "—"}</td>
                      <td className="sp-data-table__text">{s.full_name}</td>
                      {s.scores.map((score, i) => (
                        <td key={blocks.sections[i].section_id} title={
                          s.correct_counts[i] !== null
                            ? `${s.correct_counts[i]}/${blocks.sections[i].question_count} ${t("blocks.correct").toLowerCase()}`
                            : undefined
                        }>
                          {score === null ? "—" : formatPoints(score)}
                        </td>
                      ))}
                      {blocks.shows_total && (
                        <>
                          <td className="sp-data-table__strong">{s.total === null ? "—" : formatPoints(s.total)}</td>
                          <td>
                            {s.total === null || !blocks.max_total ? "—" : `${Math.round((100 * s.total) / blocks.max_total)}%`}
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          ranking &&
          ranking.rankings.length > 0 && (
            <>
              <h2 className="h4" style={{ marginBottom: "var(--space-4)" }}>
                {t("ranking.title")}
              </h2>
              <div className="row-stack" style={{ marginBottom: "var(--space-8)" }}>
                {ranking.rankings.map((r) => (
                  <ListRow
                    key={r.student_id}
                    leading={<RankBadge rank={r.rank_in_class} />}
                    title={r.full_name}
                    trailing={
                      // The share of the points, not the percentile this used
                      // to show: "0 ball · 100%" for the only student who sat
                      // the exam read as a perfect score.
                      <span className="data-value">
                        {formatPoints(r.score)} / {formatPoints(r.max_score)}
                        {r.max_score > 0 && ` · ${Math.round((100 * r.score) / r.max_score)}%`}
                      </span>
                    }
                  />
                ))}
              </div>
            </>
          )
        )}

        {stats && stats.students_graded > 0 && stats.questions.length > 0 && (
          <div style={{ marginBottom: "var(--space-8)" }}>
            <div className="sp-page-head" style={{ marginBottom: "var(--space-3)" }}>
              <div>
                <h2 className="h4">{t("stats.title")}</h2>
                <p className="body-sm ink-muted">{t("stats.subtitle", { count: stats.students_graded })}</p>
              </div>
              <div className="no-print" style={{ display: "flex", gap: "var(--space-2)" }}>
                <Button size="sm" variant={statsOrder === "hardest" ? "secondary" : "ghost"} onClick={() => setStatsOrder("hardest")}>
                  {t("stats.orderHardest")}
                </Button>
                <Button size="sm" variant={statsOrder === "paper" ? "secondary" : "ghost"} onClick={() => setStatsOrder("paper")}>
                  {t("stats.orderPaper")}
                </Button>
              </div>
            </div>
            <div className="sp-table-scroll">
              <table className="sp-data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th className="sp-data-table__text">{t("stats.question")}</th>
                    <th>{t("stats.correct")}</th>
                    <th>{t("stats.wrong")}</th>
                    <th>{t("stats.blank")}</th>
                    <th className="sp-data-table__text">{t("stats.share")}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...stats.questions]
                    .sort((a, b) =>
                      statsOrder === "hardest" ? a.correct_percent - b.correct_percent || a.number - b.number : a.number - b.number
                    )
                    .map((q) => {
                      const tone =
                        q.correct_percent < 50 ? "var(--danger)" : q.correct_percent < 70 ? "var(--warning)" : "var(--success)";
                      const open = openQuestionId === q.question_id;
                      return (
                        <tr
                          key={q.question_id}
                          className="sp-stats-row"
                          onClick={() => setOpenQuestionId(open ? null : q.question_id)}
                        >
                          <td>{q.number}</td>
                          <td className="sp-data-table__text sp-stats-row__question">
                            {q.subject_name && <span className="sp-block-table__kind" style={{ marginLeft: 0, marginRight: 8 }}>{q.subject_name}</span>}
                            <span className={open ? undefined : "sp-stats-row__clip"}>
                              {q.has_image ? t("stats.imageQuestion") : <RichText text={q.prompt_text} />}
                            </span>
                            {open && q.options.length > 0 && (
                              <ul className="sp-stats-options">
                                {q.options.map((o, i) => (
                                  <li key={i} style={{ color: o.is_correct ? "var(--success)" : undefined }}>
                                    <span className="sp-stats-options__count">{o.picked}</span>
                                    {o.is_correct ? "✓ " : ""}
                                    {o.option_text ? <RichText text={o.option_text} /> : "—"}
                                  </li>
                                ))}
                              </ul>
                            )}
                          </td>
                          <td>{q.correct}</td>
                          <td>{q.wrong}</td>
                          <td>{q.blank}</td>
                          <td className="sp-data-table__text">
                            <span className="sp-stats-bar">
                              <span style={{ width: `${q.correct_percent}%`, background: tone }} />
                            </span>
                            <span style={{ color: tone, fontFamily: "var(--font-mono)" }}>{Math.round(q.correct_percent)}%</span>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
            <p className="caption no-print" style={{ marginTop: "var(--space-2)" }}>
              {t("stats.clickHint")}
            </p>
          </div>
        )}

        <div className="no-print">
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
                          {formatPoints(a.score)} {t("result.points")}
                        </span>
                      )}
                      {a.pending_manual_count > 0 && (
                        <Badge status="warning">{t("ranking.pendingManual", { count: a.pending_manual_count })}</Badge>
                      )}
                      <Badge status={badge.status}>{badge.key ? t(badge.key) : a.status}</Badge>
                      {isDone(a.status) && exam && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/admin/exams/${id}/attempts/${a.student_id}/review`)}
                        >
                          {t("ranking.reviewAnswers")}
                        </Button>
                      )}
                      {isAdmin && a.status !== "not_started" && (
                        <ConfirmButton
                          label={t("ranking.deleteAttempt")}
                          confirmLabel={t("common.confirmDelete")}
                          onConfirm={() => handleDeleteAttempt(a.student_id)}
                        />
                      )}
                    </>
                  }
                />
              );
            })}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
