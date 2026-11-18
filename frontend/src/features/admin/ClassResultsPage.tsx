/** A whole class on one page, for the class's teachers and the admin: a results
 * table over a period (a day, a week, a chorak, the year, any range) and the
 * class's dynamics across the school year. A subject teacher gets only their
 * own subjects (the server decides — this page just shows what it was sent);
 * the homeroom teacher and the admin get every subject. */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getClassDynamics,
  getClassResults,
  type ClassDynamics,
  type ClassResults,
} from "../../api/classResultsApi";
import type { DynamicsPoint, DynamicsQuarter, DynamicsSubject } from "../../api/dynamicsApi";
import { Heatmap, QuarterBars, Radar, Ring, Timeline } from "../../components/dynamics/charts";
import { subjectColors } from "../../components/dynamics/palette";
import { useReducedMotion, useTween } from "../../components/dynamics/useMotion";
import { AdminLayout, Button, Card, EmptyState, Logo, StatCard } from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";
import { exportA4Image } from "../../utils/exportA4Image";
import { formatDateShortUz, formatDateUz } from "../../utils/formatDate";
import { formatPoints } from "../../utils/formatPoints";
import sparkMarkRed from "../../assets/logos/spetion-mark-red.png";
import "../../components/dynamics/dynamics.css";

// The table card is captured as an image (shared to Telegram), so — like the
// daily-results card — it is styled with fixed colours, never CSS variables.
const INK = "#1a1a1a";
const MUTED = "#6b6b6b";
const BRAND = "#dd1808";
const BORDER = "#ececec";
const ZEBRA = "#fdf5f4";
const MEDAL: Record<number, string> = { 1: "#f0c419", 2: "#c7cbd1", 3: "#d1904a" };

function pill(percent: number): { bg: string; fg: string } {
  if (percent < 50) return { bg: "#fbe9e7", fg: "#b11306" };
  if (percent < 70) return { bg: "#fdf0e0", fg: "#b36205" };
  return { bg: "#e9f6ee", fg: "#2f9e5b" };
}

const pad = (n: number) => String(n).padStart(2, "0");
const isoOf = (d: Date) => `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
/** Today in school time (UTC+5), as YYYY-MM-DD. */
function schoolToday(): string {
  return isoOf(new Date(Date.now() + 5 * 3600_000));
}
function shiftDays(iso: string, days: number): string {
  return isoOf(new Date(Date.parse(`${iso}T00:00:00Z`) + days * 86_400_000));
}

type Period = { key: string; start?: string; end?: string };

export default function ClassResultsPage() {
  const { classId } = useParams();
  const id = Number(classId);
  const { t } = useLanguage();
  const [tab, setTab] = useState<"table" | "dynamics">("table");
  const [year, setYear] = useState<number | undefined>(undefined);
  const [dyn, setDyn] = useState<ClassDynamics | null>(null);
  const [period, setPeriod] = useState<Period | null>(null);
  const [custom, setCustom] = useState<{ start: string; end: string }>({ start: "", end: "" });
  const [results, setResults] = useState<ClassResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const captureRef = useRef<HTMLDivElement>(null);

  // the dynamics carry the chorak calendar, which the period picker needs
  useEffect(() => {
    let cancelled = false;
    getClassDynamics(id, year)
      .then((d) => {
        if (cancelled) return;
        setDyn(d);
        setError(null);
      })
      .catch(() => !cancelled && setError(t("classRes.loadError")));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, year]);

  // first load: open on the chorak that is running (or the latest that started)
  useEffect(() => {
    if (!dyn || period) return;
    const today = schoolToday();
    const started = dyn.quarters.filter((q) => q.start_date <= today);
    const current = started.length ? started[started.length - 1] : dyn.quarters[0];
    setPeriod({ key: `q${current.number}` });
  }, [dyn, period]);

  const range = useMemo(() => {
    if (!period || !dyn) return null;
    const today = schoolToday();
    if (period.key === "today") return { start: today, end: today };
    if (period.key === "week") return { start: shiftDays(today, -6), end: today };
    if (period.key === "year") return {};
    if (period.key === "custom") return custom.start && custom.end ? { start: custom.start, end: custom.end } : null;
    const q = dyn.quarters.find((x) => `q${x.number}` === period.key);
    return q ? { start: q.start_date, end: q.end_date } : {};
  }, [period, dyn, custom]);

  useEffect(() => {
    if (!range || !dyn) return;
    let cancelled = false;
    setResults(null);
    getClassResults(id, { ...range, school_year: dyn.school_year_start })
      .then((r) => !cancelled && setResults(r))
      .catch(() => !cancelled && setError(t("classRes.loadError")));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, range, dyn?.school_year_start]);

  const download = useCallback(async () => {
    if (!captureRef.current || !results) return;
    setExporting(true);
    try {
      await exportA4Image(captureRef.current, `${results.class_name}-${results.start_date}_${results.end_date}.png`);
    } catch {
      setError(t("dailyResults.downloadError"));
    } finally {
      setExporting(false);
    }
  }, [results, t]);

  const yearLabel = (y: number) => `${y}/${String(y + 1).slice(2)}`;
  const presets: { key: string; label: string }[] = [
    { key: "today", label: t("classRes.today") },
    { key: "week", label: t("classRes.week") },
    ...[1, 2, 3, 4].map((n) => ({ key: `q${n}`, label: t("classRes.quarterN", { n }) })),
    { key: "year", label: t("classRes.wholeYear") },
    { key: "custom", label: t("classRes.custom") },
  ];

  return (
    <AdminLayout>
      <div className="page" style={{ maxWidth: 1400 }}>
        <Link to={`/classes/${id}`} className="body-sm no-print" style={{ display: "inline-block", marginBottom: "var(--space-3)" }}>
          &larr; {t("classDetail.backToClasses")}
        </Link>
        <div className="sp-dyn-head">
          <div>
            <h1 className="h2">{t("classRes.title")}</h1>
            <p className="body-sm ink-muted">
              {dyn ? dyn.class_name : ""}
              {dyn && ` · ${t("dyn.schoolYear", { year: yearLabel(dyn.school_year_start) })}`}
            </p>
            {dyn && !dyn.scope.all_subjects && <p className="caption">{t("classRes.ownSubjectsOnly")}</p>}
          </div>
          <div className="no-print" style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap", alignItems: "center" }}>
            {dyn && dyn.available_school_years.length > 1 && (
              <select
                className="sp-input"
                style={{ width: "auto" }}
                value={dyn.school_year_start}
                aria-label={t("dyn.pickYear")}
                onChange={(e) => {
                  setPeriod(null);
                  setResults(null);
                  setYear(Number(e.target.value));
                }}
              >
                {dyn.available_school_years.map((y) => (
                  <option key={y} value={y}>
                    {t("dyn.schoolYear", { year: yearLabel(y) })}
                  </option>
                ))}
              </select>
            )}
            <Link to={`/classes/${id}/daily-results`} className="body-sm">
              {t("dailyResults.navLink")}
            </Link>
          </div>
        </div>

        {error && (
          <p role="alert" style={{ color: "var(--danger)", marginBottom: "var(--space-4)" }}>
            {error}
          </p>
        )}
        {!dyn && !error && <p className="ink-muted">{t("taking.loading")}</p>}

        {dyn && (
          <>
            <div className="sp-dyn-chips no-print" role="tablist" style={{ marginBottom: "var(--space-4)" }}>
              {(["table", "dynamics"] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  role="tab"
                  aria-selected={tab === k}
                  className={`sp-dyn-chip${tab === k ? "" : " sp-dyn-chip--off"}`}
                  onClick={() => setTab(k)}
                >
                  {k === "table" ? t("classRes.tabTable") : t("classRes.tabDynamics")}
                </button>
              ))}
            </div>

            {tab === "table" && (
              <>
                <div className="no-print" style={{ marginBottom: "var(--space-4)" }}>
                  <div className="sp-dyn-chips">
                    {presets.map((p) => (
                      <button
                        key={p.key}
                        type="button"
                        className={`sp-dyn-chip${period?.key === p.key ? "" : " sp-dyn-chip--off"}`}
                        aria-pressed={period?.key === p.key}
                        onClick={() => setPeriod({ key: p.key })}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                  {period?.key === "custom" && (
                    <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center", marginTop: "var(--space-2)", flexWrap: "wrap" }}>
                      <input
                        type="date"
                        className="sp-input"
                        style={{ width: "auto" }}
                        value={custom.start}
                        aria-label={t("classRes.from")}
                        onChange={(e) => setCustom({ ...custom, start: e.target.value })}
                      />
                      <span className="ink-muted">—</span>
                      <input
                        type="date"
                        className="sp-input"
                        style={{ width: "auto" }}
                        value={custom.end}
                        aria-label={t("classRes.to")}
                        onChange={(e) => setCustom({ ...custom, end: e.target.value })}
                      />
                    </div>
                  )}
                </div>

                {range === null && <p className="body-sm ink-muted">{t("classRes.pickDates")}</p>}
                {range !== null && !results && !error && <p className="ink-muted">{t("taking.loading")}</p>}
                {results && (
                  <>
                    <div className="no-print" style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
                      <Button size="sm" onClick={download} disabled={exporting || results.columns.length === 0}>
                        {exporting ? t("dailyResults.exporting") : t("dailyResults.download")}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => window.print()} disabled={results.columns.length === 0}>
                        {t("classRes.print")}
                      </Button>
                    </div>
                    {results.columns.length === 0 ? (
                      <EmptyState icon="inbox" title={t("classRes.empty")} />
                    ) : (
                      <div style={{ overflowX: "auto" }}>
                        <ResultsCard results={results} cardRef={captureRef} />
                      </div>
                    )}
                  </>
                )}
              </>
            )}

            {tab === "dynamics" && <DynamicsTab data={dyn} />}
          </>
        )}
      </div>
    </AdminLayout>
  );
}

function ResultsCard({ results, cardRef }: { results: ClassResults; cardRef: React.RefObject<HTMLDivElement> }) {
  const { t } = useLanguage();
  const cols = results.columns;
  const period =
    results.start_date === results.end_date
      ? formatDateUz(results.start_date)
      : `${formatDateShortUz(results.start_date)} — ${formatDateShortUz(results.end_date)}`;
  const top = results.students.find((s) => s.rank === 1 && s.percent !== null);
  return (
    <div
      ref={cardRef}
      style={{
        position: "relative",
        backgroundColor: "#ffffff",
        color: INK,
        borderRadius: 12,
        width: "fit-content",
        minWidth: 560,
        border: `1px solid ${BORDER}`,
        fontFamily: "Inter, system-ui, sans-serif",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `url(${sparkMarkRed})`,
          backgroundRepeat: "repeat",
          backgroundSize: "70px 70px",
          opacity: 0.05,
        }}
      />
      <div style={{ position: "relative" }}>
        <div style={{ height: 8, background: BRAND }} />
        <div style={{ padding: "24px 28px 8px", textAlign: "left" }}>
          <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 12 }}>
            <Logo tone="red" height={28} />
          </div>
          <h2 style={{ fontSize: 24, letterSpacing: 1, margin: 0, marginBottom: 4 }}>
            {t("classRes.cardTitle", { className: results.class_name.toUpperCase() })}
          </h2>
          <p style={{ fontSize: 14, color: MUTED, margin: 0, marginBottom: 14 }}>
            {period}
            {results.class_percent !== null && ` · ${t("classRes.classAverage")}: ${Math.round(results.class_percent)}%`}
          </p>
          {top && (
            <p style={{ fontSize: 14, margin: "0 0 14px" }}>
              ★ <b>{top.full_name}</b> — {Math.round(top.percent ?? 0)}%
            </p>
          )}
        </div>
        <div style={{ padding: "0 28px 18px" }}>
          <table style={{ borderCollapse: "collapse", fontSize: 12.5, width: "100%", background: "#ffffff" }}>
            <thead>
              <tr style={{ background: BRAND, color: "#ffffff" }}>
                <th style={{ padding: "8px 8px", fontSize: 12 }}>T/R</th>
                <th style={{ textAlign: "left", padding: "8px 8px", fontSize: 12 }}>{t("dailyResults.studentColumn")}</th>
                {cols.map((c) => (
                  <th key={`${c.exam_id}-${c.subject_id}`} style={{ padding: "6px 8px", fontSize: 12, whiteSpace: "nowrap", verticalAlign: "bottom" }}>
                    <div>{c.subject_name}</div>
                    <div style={{ fontSize: 10.5, fontWeight: 400, opacity: 0.85 }}>
                      {formatDateShortUz(c.date)}
                      {c.exam_type === "chorak" ? ` · ${t("examType.chorakShort")}` : ""}
                    </div>
                    <div style={{ fontSize: 10, fontWeight: 400, opacity: 0.7 }}>/{formatPoints(c.max_score)}</div>
                  </th>
                ))}
                <th style={{ padding: "8px 8px", fontSize: 12 }}>{t("dailyResults.totalColumn")}</th>
              </tr>
            </thead>
            <tbody>
              {results.students.map((row, rowIndex) => {
                const p = row.percent === null ? null : pill(row.percent);
                return (
                  <tr key={row.student_id} style={{ background: rowIndex % 2 === 1 ? ZEBRA : "#ffffff" }}>
                    <td style={{ padding: "7px 8px", textAlign: "center" }}>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          minWidth: 22,
                          height: 22,
                          borderRadius: 999,
                          fontSize: 12,
                          fontWeight: 700,
                          background: row.rank !== null ? MEDAL[row.rank] ?? "transparent" : "transparent",
                          color: row.rank !== null && MEDAL[row.rank] ? INK : MUTED,
                        }}
                      >
                        {row.rank ?? "—"}
                      </span>
                    </td>
                    <td style={{ padding: "7px 8px", whiteSpace: "nowrap", fontWeight: 600 }}>{row.full_name}</td>
                    {row.cells.map((cell, i) => {
                      const cp = cell ? pill(cell.percent) : null;
                      return (
                        <td
                          key={`${cols[i].exam_id}-${cols[i].subject_id}`}
                          title={cell ? `${formatPoints(cell.score)} / ${formatPoints(cell.max_score)}` : undefined}
                          style={{ padding: "7px 8px", textAlign: "center", fontFamily: "'Space Mono', monospace", color: cp ? cp.fg : MUTED, fontWeight: cp ? 700 : 400 }}
                        >
                          {cell ? `${Math.round(cell.percent)}%` : "—"}
                        </td>
                      );
                    })}
                    <td style={{ padding: "7px 8px", textAlign: "center" }}>
                      {p ? (
                        <span style={{ display: "inline-block", padding: "3px 10px", borderRadius: 999, fontSize: 13, fontWeight: 700, background: p.bg, color: p.fg }}>
                          {Math.round(row.percent ?? 0)}%
                        </span>
                      ) : (
                        <span style={{ fontSize: 12, color: MUTED, fontStyle: "italic" }}>{t("dailyResults.notParticipated")}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
              <tr style={{ borderTop: `2px solid ${BRAND}`, fontWeight: 700 }}>
                <td />
                <td style={{ padding: "8px 8px" }}>{t("classRes.classAverage")}</td>
                {cols.map((c) => (
                  <td key={`${c.exam_id}-${c.subject_id}`} style={{ padding: "8px 8px", textAlign: "center", fontFamily: "'Space Mono', monospace" }}>
                    {c.class_percent === null ? "—" : `${Math.round(c.class_percent)}%`}
                  </td>
                ))}
                <td style={{ padding: "8px 8px", textAlign: "center", fontFamily: "'Space Mono', monospace" }}>
                  {results.class_percent === null ? "—" : `${Math.round(results.class_percent)}%`}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style={{ padding: "10px 28px", borderTop: `1px solid ${BORDER}`, textAlign: "center", fontSize: 12, color: MUTED }}>
          {t("classRes.footer", { students: results.students.length, exams: cols.length })}
        </div>
      </div>
    </div>
  );
}

type SortKey = "rank" | "name" | "baseline" | "current" | "delta" | "exams";

function DynamicsTab({ data }: { data: ClassDynamics }) {
  const { t } = useLanguage();
  const animate = !useReducedMotion();
  const tween = useTween(animate);
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "rank", dir: 1 });
  const [visible, setVisible] = useState<Set<number> | null>(null);

  // The class's own numbers wear the student page's clothes, so the very same
  // charts draw them (a class average is just a result with no class beside it).
  const points: DynamicsPoint[] = useMemo(
    () =>
      data.timeline.map((c) => ({
        exam_id: c.exam_id,
        exam_title: c.exam_title,
        exam_type: c.exam_type,
        subject_id: c.subject_id,
        subject_name: c.subject_name,
        date: c.date,
        quarter: Number(data.quarters.find((q) => q.start_date <= c.date && c.date <= q.end_date)?.number ?? 4),
        score: 0,
        max_score: c.max_score,
        percent: c.class_percent ?? 0,
        class_percent: null,
        provisional: false,
      })),
    [data]
  );
  const subjects: DynamicsSubject[] = data.subjects.map((s) => ({ ...s, class_percent: null }));
  const quarters: DynamicsQuarter[] = data.quarters.map((q) => ({ ...q, rank: null, rank_of: null }));
  const colors = useMemo(() => subjectColors(data.subjects.map((s) => s.subject_id)), [data.subjects]);
  const shown = visible ?? new Set(data.subjects.map((s) => s.subject_id));
  const toggle = (sid: number) => {
    const next = new Set(shown);
    if (next.has(sid)) next.delete(sid);
    else next.add(sid);
    setVisible(next);
  };

  const rows = useMemo(() => {
    const value = (s: ClassDynamics["students"][number]): number | string => {
      switch (sort.key) {
        case "name":
          return s.full_name.toLowerCase();
        case "baseline":
          return s.baseline_percent ?? -1;
        case "current":
          return s.current_percent ?? -1;
        case "delta":
          return s.delta ?? -999;
        case "exams":
          return s.exams_count;
        default:
          return s.rank ?? 9999;
      }
    };
    return [...data.students].sort((a, b) => {
      const x = value(a);
      const y = value(b);
      return (x < y ? -1 : x > y ? 1 : 0) * sort.dir;
    });
  }, [data.students, sort]);

  if (data.exams_count === 0) return <EmptyState icon="inbox" title={t("classRes.dynEmpty")} />;

  const th = (key: SortKey, label: string) => (
    <th
      onClick={() => setSort({ key, dir: sort.key === key ? (sort.dir === 1 ? -1 : 1) : key === "name" || key === "rank" ? 1 : -1 })}
      style={{ cursor: "pointer", textAlign: key === "name" ? "left" : "right", padding: "8px 10px", whiteSpace: "nowrap" }}
      aria-sort={sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
    >
      {label}
      {sort.key === key ? (sort.dir === 1 ? " ▲" : " ▼") : ""}
    </th>
  );
  const withChange = data.subjects.filter((s) => s.delta !== null);

  return (
    <div className="sp-dyn">
      <Card>
        <div className="sp-dyn-hero">
          <Ring value={data.current_percent} animate={animate} />
          <div className="stack" style={{ gap: "var(--space-3)", flex: 1, minWidth: 240 }}>
            <div>
              <div className="data-eyebrow">{t("classRes.classLevel")}</div>
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap", marginTop: 4 }}>
                <DeltaChip delta={data.delta} />
                {data.delta !== null && data.baseline_percent !== null && data.current_percent !== null && (
                  <span className="body-sm ink-muted">
                    {t("dyn.fromTo", { from: Math.round(data.baseline_percent), to: Math.round(data.current_percent) })}
                  </span>
                )}
              </div>
            </div>
            <div className="sp-statcard-grid">
              <StatCard label={t("classRes.studentsCount")} value={data.students_count} />
              <StatCard label={t("dyn.examsCount")} value={data.exams_count} />
              <StatCard label={t("classRes.bandHigh")} value={data.bands.high} tone="success" />
              <StatCard label={t("classRes.bandMiddle")} value={data.bands.middle} tone="warning" />
              <StatCard label={t("classRes.bandLow")} value={data.bands.low} tone="danger" />
            </div>
          </div>
        </div>
      </Card>

      <div className="sp-dyn-two">
        <Card className="stack">
          <div>
            <h2 className="h4">{t("classRes.radarTitle")}</h2>
            <p className="body-sm ink-muted">{t("dyn.radarHint")}</p>
          </div>
          {subjects.length >= 3 && withChange.length > 0 ? (
            <>
              <Radar subjects={subjects} t={tween.t} />
              <input
                className="sp-dyn-slider"
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={tween.t}
                aria-label={t("classRes.radarTitle")}
                onChange={(e) => tween.setT(Number(e.target.value))}
              />
              <div className="sp-dyn-slider-labels">
                <span>{t("dyn.yearStart")}</span>
                <Button variant="ghost" size="sm" onClick={tween.play} disabled={tween.playing}>
                  ▶ {t("dyn.play")}
                </Button>
                <span>{t("dyn.now")}</span>
              </div>
            </>
          ) : (
            <div className="stack" style={{ gap: "var(--space-2)" }}>
              {subjects.map((s) => (
                <div key={s.subject_id} className="sp-dyn-subject__row">
                  <span className="body-sm">{s.subject_name}</span>
                  <span className="data-value">{Math.round(s.current_percent)}%</span>
                </div>
              ))}
              <p className="caption">{t("dyn.radarNeedsMore")}</p>
            </div>
          )}
        </Card>
        <Card className="stack">
          <div>
            <h2 className="h4">{t("dyn.quartersTitle")}</h2>
            <p className="body-sm ink-muted">{t("classRes.quartersHint")}</p>
          </div>
          <QuarterBars quarters={quarters} showRank={false} animate={animate} />
        </Card>
      </div>

      <Card>
        <h2 className="h4">{t("classRes.timelineTitle")}</h2>
        <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-3)" }}>
          {t("classRes.timelineHint")}
        </p>
        <div className="sp-dyn-chips">
          {data.subjects.map((s) => (
            <button
              key={s.subject_id}
              type="button"
              className={`sp-dyn-chip${shown.has(s.subject_id) ? "" : " sp-dyn-chip--off"}`}
              onClick={() => toggle(s.subject_id)}
              aria-pressed={shown.has(s.subject_id)}
            >
              <span className="sp-dyn-chip__dot" style={{ background: colors.get(s.subject_id) }} />
              {s.subject_name}
            </button>
          ))}
        </div>
        <Timeline
          key={`${data.school_year_start}-${data.class_id}`}
          points={points}
          missed={[]}
          quarters={quarters}
          schoolYearStart={data.school_year_start}
          colors={colors}
          visible={shown}
          showOverall
          showClassOverall={false}
          showClassBySubject={false}
          animate={animate}
        />
      </Card>

      <Card>
        <h2 className="h4">{t("dyn.heatmapTitle")}</h2>
        <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-3)" }}>
          {t("classRes.heatmapHint")}
        </p>
        <Heatmap points={points} />
      </Card>

      <Card>
        <h2 className="h4">{t("classRes.subjectsTitle")}</h2>
        <div style={{ overflowX: "auto", marginTop: "var(--space-3)" }}>
          <table className="sp-table" style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr className="body-sm ink-muted">
                <th style={{ textAlign: "left", padding: "8px 10px" }}>{t("classRes.colSubject")}</th>
                <th style={{ textAlign: "right", padding: "8px 10px" }}>{t("dyn.yearStart")}</th>
                <th style={{ textAlign: "right", padding: "8px 10px" }}>{t("dyn.now")}</th>
                <th style={{ textAlign: "right", padding: "8px 10px" }}>{t("classRes.colChange")}</th>
                <th style={{ textAlign: "right", padding: "8px 10px" }}>{t("dyn.examsCount")}</th>
              </tr>
            </thead>
            <tbody>
              {[...data.subjects].sort((a, b) => a.current_percent - b.current_percent).map((s) => (
                <tr key={s.subject_id} style={{ borderTop: "1px solid var(--border)" }}>
                  <td style={{ padding: "8px 10px" }}>
                    <span className="sp-dyn-chip__dot" style={{ background: colors.get(s.subject_id), display: "inline-block", marginRight: 8 }} />
                    {s.subject_name}
                  </td>
                  <td className="data-value" style={{ textAlign: "right", padding: "8px 10px" }}>{Math.round(s.baseline_percent)}%</td>
                  <td className="data-value" style={{ textAlign: "right", padding: "8px 10px", color: pill(s.current_percent).fg }}>{Math.round(s.current_percent)}%</td>
                  <td style={{ textAlign: "right", padding: "8px 10px" }}><DeltaChip delta={s.delta} /></td>
                  <td className="data-value" style={{ textAlign: "right", padding: "8px 10px" }}>{s.exams_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <h2 className="h4">{t("classRes.studentsTitle")}</h2>
        <p className="body-sm ink-muted">{t("classRes.studentsHint")}</p>
        <div style={{ overflowX: "auto", marginTop: "var(--space-3)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr className="body-sm ink-muted">
                {th("rank", "#")}
                {th("name", t("dailyResults.studentColumn"))}
                {th("baseline", t("dyn.yearStart"))}
                {th("current", t("dyn.now"))}
                {th("delta", t("classRes.colChange"))}
                {th("exams", t("dyn.examsCount"))}
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.student_id} style={{ borderTop: "1px solid var(--border)" }}>
                  <td className="data-value" style={{ textAlign: "right", padding: "8px 10px" }}>{s.rank ?? "—"}</td>
                  <td style={{ padding: "8px 10px" }}>
                    <Link to={`/students/${s.student_id}/performance`}>{s.full_name}</Link>
                  </td>
                  <td className="data-value" style={{ textAlign: "right", padding: "8px 10px" }}>
                    {s.baseline_percent === null ? "—" : `${Math.round(s.baseline_percent)}%`}
                  </td>
                  <td className="data-value" style={{ textAlign: "right", padding: "8px 10px", color: s.current_percent === null ? undefined : pill(s.current_percent).fg }}>
                    {s.current_percent === null ? "—" : `${Math.round(s.current_percent)}%`}
                  </td>
                  <td style={{ textAlign: "right", padding: "8px 10px" }}><DeltaChip delta={s.delta} /></td>
                  <td className="data-value" style={{ textAlign: "right", padding: "8px 10px" }}>{s.exams_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function DeltaChip({ delta }: { delta: number | null }) {
  const { t } = useLanguage();
  if (delta === null) return <span className="sp-dyn-delta sp-dyn-delta--flat">{t("dyn.notEnough")}</span>;
  const rounded = Math.round(delta);
  const cls = rounded > 0 ? "up" : rounded < 0 ? "down" : "flat";
  return (
    <span className={`sp-dyn-delta sp-dyn-delta--${cls}`}>
      {rounded > 0 ? "▲ +" : rounded < 0 ? "▼ " : "● "}
      {rounded} {t("dyn.points")}
    </span>
  );
}
