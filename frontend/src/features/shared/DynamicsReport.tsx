/** The parent-facing A4 report (two pages). Rendered off-screen and captured
 * into a PDF — see exportPagesPdf. Fixed colours and no animation: it must look
 * the same whatever theme the teacher happens to be using. It never includes
 * the student's place in the class, whoever downloads it. */
import { forwardRef } from "react";
import type { Dynamics } from "../../api/dynamicsApi";
import { Heatmap, QuarterBars, Radar, Ring, Timeline } from "../../components/dynamics/charts";
import { PAPER, subjectColors, toneColor } from "../../components/dynamics/palette";
import { Logo } from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";
import { formatDateShortUz, formatDateUz } from "../../utils/formatDate";
import { formatPoints } from "../../utils/formatPoints";
import "../../components/dynamics/dynamics.css";

const MAX_TABLE_SUBJECTS = 12;
const MAX_LIST_ROWS = 8;

function Header({ title, right }: { title: string; right: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `2px solid ${PAPER.brand}`, paddingBottom: 12 }}>
      <Logo variant="horizontal" tone="red" height={30} />
      <div style={{ textAlign: "right" }}>
        <div style={{ fontWeight: 800, fontSize: 15 }}>{title}</div>
        <div style={{ fontSize: 11, color: PAPER.muted }}>{right}</div>
      </div>
    </div>
  );
}

function Footer({ page, of }: { page: number; of: number }) {
  const { t } = useLanguage();
  return (
    <div style={{ marginTop: "auto", display: "flex", justifyContent: "space-between", fontSize: 10, color: PAPER.muted, borderTop: `1px solid ${PAPER.border}`, paddingTop: 8 }}>
      <span>{t("report.footer", { site: window.location.host })}</span>
      <span>
        {page} / {of}
      </span>
    </div>
  );
}

const sectionTitle = { fontSize: 13, fontWeight: 800, margin: "0 0 6px" } as const;

const DynamicsReport = forwardRef<HTMLDivElement, { data: Dynamics }>(function DynamicsReport({ data }, ref) {
  const { t } = useLanguage();
  const colors = subjectColors(data.subjects.map((s) => s.subject_id));
  const everyone = new Set(data.subjects.map((s) => s.subject_id));
  const o = data.overall;
  const year = `${data.school_year_start}/${String(data.school_year_start + 1).slice(2)}`;
  const today = formatDateUz(new Date().toISOString());
  const insights = [
    data.insights.most_improved && t("report.improved", { name: data.insights.most_improved.subject_name, n: Math.round(data.insights.most_improved.value) }),
    data.insights.most_declined && t("report.declined", { name: data.insights.most_declined.subject_name, n: Math.abs(Math.round(data.insights.most_declined.value)) }),
    data.insights.strongest && t("report.strongest", { name: data.insights.strongest.subject_name, n: Math.round(data.insights.strongest.value) }),
    data.insights.weakest && t("report.weakest", { name: data.insights.weakest.subject_name, n: Math.round(data.insights.weakest.value) }),
  ].filter(Boolean) as string[];
  const subjects = data.subjects.slice(0, MAX_TABLE_SUBJECTS);
  const recent = [...data.points].reverse().slice(0, MAX_LIST_ROWS);
  const title = t("report.title");
  const radarReady = data.subjects.length >= 3 && data.subjects.some((s) => s.delta !== null);
  const hasClassData = data.points.some((p) => p.class_percent !== null);

  return (
    <div className="sp-report-host" ref={ref} aria-hidden="true">
      <div className="sp-report-page">
        <Header title={title} right={t("report.generated", { date: today })} />
        <div>
          <div style={{ fontSize: 24, fontWeight: 800 }}>{data.full_name}</div>
          <div style={{ fontSize: 13, color: PAPER.muted }}>
            {data.class_name} · {t("dyn.schoolYear", { year })}
          </div>
        </div>

        <div style={{ display: "flex", gap: 22, alignItems: "center" }}>
          <Ring value={o.current_percent} size={128} paper animate={false} />
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
              {[
                [t("dyn.overall"), o.current_percent === null ? "—" : `${Math.round(o.current_percent)}%`],
                [
                  t("report.change"),
                  o.delta === null ? "—" : `${o.delta > 0 ? "+" : ""}${Math.round(o.delta)} ${t("dyn.points")}`,
                ],
                [t("dyn.examsCount"), String(o.exams_count)],
                [t("dyn.average"), o.average_percent === null ? "—" : `${Math.round(o.average_percent)}%`],
                ...(o.class_percent !== null ? [[t("dyn.classAvg"), `${Math.round(o.class_percent)}%`]] : []),
              ].map(([label, value]) => (
                <div key={label}>
                  <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.05em", color: PAPER.muted, fontWeight: 700 }}>{label}</div>
                  <div style={{ fontSize: 20, fontWeight: 800, fontFamily: "var(--font-mono)", color: label === t("report.change") && o.delta !== null ? (o.delta >= 0 ? PAPER.success : PAPER.danger) : PAPER.ink }}>{value}</div>
                </div>
              ))}
            </div>
            {o.delta !== null && o.baseline_percent !== null && o.current_percent !== null && (
              <div style={{ fontSize: 12, color: PAPER.muted }}>
                {t("dyn.fromTo", { from: Math.round(o.baseline_percent), to: Math.round(o.current_percent) })}
              </div>
            )}
            {insights.map((line) => (
              <div key={line} style={{ fontSize: 12, lineHeight: "17px" }}>
                • {line}
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, alignItems: "start" }}>
          <div>
            <h3 style={sectionTitle}>{t("dyn.radarTitle")}</h3>
            {radarReady ? (
              <Radar subjects={data.subjects} t={1} paper size={340} />
            ) : (
              <div style={{ fontSize: 11, color: PAPER.muted }}>{t("dyn.radarNeedsMore")}</div>
            )}
            {radarReady && <div style={{ fontSize: 10, color: PAPER.muted, textAlign: "center" }}>┅ {t("dyn.yearStart")} · ▬ {t("dyn.now")}</div>}
          </div>
          <div>
            <h3 style={sectionTitle}>{t("dyn.quartersTitle")}</h3>
            <QuarterBars quarters={data.quarters} showRank={false} paper animate={false} />
          </div>
        </div>

        <div>
          <h3 style={sectionTitle}>{t("dyn.subjectsTitle")}</h3>
          <table className="sp-report-table">
            <thead>
              <tr>
                <th>{t("blocks.subject")}</th>
                <th>{t("report.colStart")}</th>
                <th>{t("report.colNow")}</th>
                <th>{t("report.change")}</th>
                <th>{t("dyn.classAvg")}</th>
                <th>{t("dyn.examsCount")}</th>
              </tr>
            </thead>
            <tbody>
              {subjects.map((s) => (
                <tr key={s.subject_id}>
                  <td>
                    <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 4, background: colors.get(s.subject_id), marginRight: 6 }} />
                    {s.subject_name}
                  </td>
                  <td>{Math.round(s.baseline_percent)}%</td>
                  <td style={{ fontWeight: 800, color: toneColor(s.current_percent, PAPER) }}>{Math.round(s.current_percent)}%</td>
                  <td style={{ color: s.delta === null ? PAPER.muted : s.delta >= 0 ? PAPER.success : PAPER.danger, fontWeight: 700 }}>
                    {s.delta === null ? "—" : `${s.delta > 0 ? "+" : ""}${Math.round(s.delta)}`}
                  </td>
                  <td>{s.class_percent === null ? "—" : `${Math.round(s.class_percent)}%`}</td>
                  <td>{s.exams_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.subjects.length > MAX_TABLE_SUBJECTS && (
            <div style={{ fontSize: 10, color: PAPER.muted, marginTop: 4 }}>{t("report.more", { n: data.subjects.length - MAX_TABLE_SUBJECTS })}</div>
          )}
        </div>
        <Footer page={1} of={2} />
      </div>

      <div className="sp-report-page">
        <Header title={title} right={`${data.full_name} · ${data.class_name}`} />
        <div>
          <h3 style={sectionTitle}>{t("dyn.timelineTitle")}</h3>
          <Timeline
            points={data.points}
            missed={data.missed}
            quarters={data.quarters}
            schoolYearStart={data.school_year_start}
            colors={colors}
            visible={everyone}
            showOverall
            showClassOverall={hasClassData}
            showClassBySubject={false}
            paper
            animate={false}
          />
          <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 14px", fontSize: 10, color: PAPER.muted }}>
            {data.subjects.map((s) => (
              <span key={s.subject_id}>
                <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 4, background: colors.get(s.subject_id), marginRight: 4 }} />
                {s.subject_name}
              </span>
            ))}
            <span>━ {t("dyn.legendOverall")}</span>
            {hasClassData && <span>┅ {t("dyn.legendClass")}</span>}
            <span>● {t("dyn.legendNazorat")}</span>
            <span>⬤ {t("dyn.legendChorak")}</span>
            {data.missed.length > 0 && <span style={{ color: PAPER.danger }}>× {t("dyn.legendMissed")}</span>}
          </div>
        </div>
        <div>
          <h3 style={sectionTitle}>{t("dyn.heatmapTitle")}</h3>
          <Heatmap points={data.points} paper />
        </div>
        <div>
          <h3 style={sectionTitle}>{t("report.recent")}</h3>
          <table className="sp-report-table">
            <thead>
              <tr>
                <th>{t("dyn.colExam")}</th>
                <th>{t("blocks.subject")}</th>
                <th>{t("dyn.colDate")}</th>
                <th>{t("blocks.score")}</th>
                <th>%</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((p) => (
                <tr key={`${p.exam_id}-${p.subject_id}`}>
                  <td>{p.exam_title}</td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-sans)" }}>{p.subject_name}</td>
                  <td>{formatDateShortUz(`${p.date}T00:00:00`)}</td>
                  <td>
                    {formatPoints(p.score)}/{formatPoints(p.max_score)}
                  </td>
                  <td style={{ color: toneColor(p.percent, PAPER), fontWeight: 700 }}>{Math.round(p.percent)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.points.length > MAX_LIST_ROWS && (
            <div style={{ fontSize: 10, color: PAPER.muted, marginTop: 4 }}>{t("report.more", { n: data.points.length - MAX_LIST_ROWS })}</div>
          )}
        </div>
        <Footer page={2} of={2} />
      </div>
    </div>
  );
});

export default DynamicsReport;
