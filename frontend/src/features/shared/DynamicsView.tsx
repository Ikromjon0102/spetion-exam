/** One student's learning dynamics on one page: where the year started, where
 * the student is now, subject by subject and chorak by chorak. The same page
 * for the student, the teacher and the admin; only a teacher/admin also sees
 * the place in the class (the server doesn't send it to a student at all). */
import { useMemo, useState } from "react";
import type { Dynamics, DynamicsSubject } from "../../api/dynamicsApi";
import { Badge, Button, Card } from "../../components/ui";
import { Heatmap, MiniSpark, QuarterBars, Radar, Ring, Timeline } from "../../components/dynamics/charts";
import { APP, subjectColors, toneColor } from "../../components/dynamics/palette";
import { useReducedMotion, useTween } from "../../components/dynamics/useMotion";
import { useLanguage } from "../../i18n/LanguageContext";
import { formatDateShortUz } from "../../utils/formatDate";
import { formatPoints } from "../../utils/formatPoints";
import "../../components/dynamics/dynamics.css";

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

interface Props {
  data: Dynamics;
  onYearChange: (year: number) => void;
  onDownloadPdf: () => void;
  exporting: boolean;
}

export default function DynamicsView({ data, onYearChange, onDownloadPdf, exporting }: Props) {
  const { t } = useLanguage();
  const reduced = useReducedMotion();
  const animate = !reduced;

  const colors = useMemo(() => subjectColors(data.subjects.map((s) => s.subject_id)), [data.subjects]);
  const [visible, setVisible] = useState<Set<number> | null>(null);
  const shown = visible ?? new Set(data.subjects.map((s) => s.subject_id));
  const [showOverall, setShowOverall] = useState(true);
  const [showClassOverall, setShowClassOverall] = useState(true);
  const [showClassBySubject, setShowClassBySubject] = useState(false);
  const [filterSubject, setFilterSubject] = useState<number | "">("");
  const tween = useTween(animate);

  const toggle = (id: number) => {
    const next = new Set(shown);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setVisible(next);
  };

  const hasData = data.points.length > 0;
  const withChange = data.subjects.filter((s) => s.delta !== null);
  const provisionalCount = data.points.filter((p) => p.provisional).length;
  const subjectsForCards = [...data.subjects].sort((a, b) => a.current_percent - b.current_percent);
  const o = data.overall;
  const hasClassData = data.points.some((p) => p.class_percent !== null);
  const rows = [...data.points].filter((p) => filterSubject === "" || p.subject_id === filterSubject).reverse();

  const yearLabel = (y: number) => `${y}/${String(y + 1).slice(2)}`;

  return (
    <div className="sp-dyn">
      <div className="sp-dyn-head">
        <div>
          <h1 className="h2">{data.full_name}</h1>
          <p className="body-sm ink-muted">
            {data.class_name} · {t("dyn.schoolYear", { year: yearLabel(data.school_year_start) })}
          </p>
        </div>
        <div className="no-print" style={{ display: "flex", gap: "var(--space-2)", alignItems: "center", flexWrap: "wrap" }}>
          {data.available_school_years.length > 1 && (
            <select
              className="sp-input"
              style={{ width: "auto" }}
              value={data.school_year_start}
              aria-label={t("dyn.pickYear")}
              onChange={(e) => onYearChange(Number(e.target.value))}
            >
              {data.available_school_years.map((y) => (
                <option key={y} value={y}>
                  {t("dyn.schoolYear", { year: yearLabel(y) })}
                </option>
              ))}
            </select>
          )}
          <Button size="sm" onClick={onDownloadPdf} disabled={!hasData || exporting}>
            {exporting ? t("dyn.pdfMaking") : t("dyn.pdf")}
          </Button>
        </div>
      </div>

      {!hasData && (
        <Card>
          <p className="body ink-muted">{t("dyn.empty")}</p>
        </Card>
      )}

      {hasData && (
        <>
          <Card>
            <div className="sp-dyn-hero">
              <Ring value={o.current_percent} animate={animate} />
              <div className="stack" style={{ gap: "var(--space-3)", flex: 1, minWidth: 240 }}>
                <div>
                  <div className="data-eyebrow">{t("dyn.overall")}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap", marginTop: 4 }}>
                    <DeltaChip delta={o.delta} />
                    {o.delta !== null && o.baseline_percent !== null && o.current_percent !== null && (
                      <span className="body-sm ink-muted">
                        {t("dyn.fromTo", { from: Math.round(o.baseline_percent), to: Math.round(o.current_percent) })}
                      </span>
                    )}
                  </div>
                </div>
                <div className="sp-dyn-hero__facts">
                  <div>
                    <div className="data-eyebrow">{t("dyn.examsCount")}</div>
                    <div className="sp-dyn-fact__value">{o.exams_count}</div>
                  </div>
                  <div>
                    <div className="data-eyebrow">{t("dyn.average")}</div>
                    <div className="sp-dyn-fact__value" style={{ color: toneColor(o.average_percent, APP) }}>
                      {o.average_percent === null ? "—" : `${Math.round(o.average_percent)}%`}
                    </div>
                  </div>
                  {o.class_percent !== null && (
                    <div>
                      <div className="data-eyebrow">{t("dyn.classAvg")}</div>
                      <div className="sp-dyn-fact__value">{Math.round(o.class_percent)}%</div>
                    </div>
                  )}
                  {data.show_rank && o.rank !== null && (
                    <div>
                      <div className="data-eyebrow">{t("dyn.rankLabel")}</div>
                      <div className="sp-dyn-fact__value">
                        {o.rank}
                        <span className="ink-muted" style={{ fontSize: 14 }}> / {o.rank_of}</span>
                      </div>
                    </div>
                  )}
                </div>
                {(provisionalCount > 0 || data.missed.length > 0) && (
                  <div className="sp-dyn-notes">
                    {provisionalCount > 0 && <Badge status="warning">{t("dyn.provisionalN", { n: provisionalCount })}</Badge>}
                    {data.missed.length > 0 && <Badge status="neutral">{t("dyn.missedN", { n: data.missed.length })}</Badge>}
                  </div>
                )}
              </div>
            </div>
          </Card>

          {(data.insights.most_improved || data.insights.most_declined || data.insights.strongest || data.insights.weakest) && (
            <div className="sp-dyn-insights">
              {data.insights.most_improved && (
                <div className="sp-dyn-insight" style={{ borderColor: "var(--success)" }}>
                  {t("dyn.insightImproved")}
                  <b>
                    {data.insights.most_improved.subject_name} ▲ +{Math.round(data.insights.most_improved.value)}
                  </b>
                </div>
              )}
              {data.insights.most_declined && (
                <div className="sp-dyn-insight" style={{ borderColor: "var(--danger)" }}>
                  {t("dyn.insightDeclined")}
                  <b>
                    {data.insights.most_declined.subject_name} ▼ {Math.round(data.insights.most_declined.value)}
                  </b>
                </div>
              )}
              {data.insights.strongest && (
                <div className="sp-dyn-insight">
                  {t("dyn.insightStrongest")}
                  <b>
                    {data.insights.strongest.subject_name} · {Math.round(data.insights.strongest.value)}%
                  </b>
                </div>
              )}
              {data.insights.weakest && (
                <div className="sp-dyn-insight">
                  {t("dyn.insightWeakest")}
                  <b>
                    {data.insights.weakest.subject_name} · {Math.round(data.insights.weakest.value)}%
                  </b>
                </div>
              )}
            </div>
          )}

          <div className="sp-dyn-two">
            <Card className="stack">
              <div>
                <h2 className="h4">{t("dyn.radarTitle")}</h2>
                <p className="body-sm ink-muted">{t("dyn.radarHint")}</p>
              </div>
              {data.subjects.length >= 3 && withChange.length > 0 ? (
                <>
                  <Radar subjects={data.subjects} t={tween.t} />
                  <input
                    className="sp-dyn-slider"
                    type="range"
                    min={0}
                    max={1}
                    step={0.01}
                    value={tween.t}
                    aria-label={t("dyn.radarTitle")}
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
                  {data.subjects.map((s) => (
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
                <p className="body-sm ink-muted">{t("dyn.quartersHint")}</p>
              </div>
              <QuarterBars quarters={data.quarters} showRank={data.show_rank} animate={animate} />
            </Card>
          </div>

          <Card>
            <h2 className="h4">{t("dyn.timelineTitle")}</h2>
            <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-3)" }}>
              {t("dyn.timelineHint")}
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
              <button
                type="button"
                className="sp-dyn-chip sp-dyn-chip--off"
                onClick={() => setVisible(shown.size === data.subjects.length ? new Set() : new Set(data.subjects.map((s) => s.subject_id)))}
              >
                {shown.size === data.subjects.length ? t("dyn.hideAll") : t("dyn.showAll")}
              </button>
            </div>
            <Timeline
              key={`${data.school_year_start}-${data.student_id}`}
              points={data.points}
              missed={data.missed}
              quarters={data.quarters}
              schoolYearStart={data.school_year_start}
              colors={colors}
              visible={shown}
              showOverall={showOverall}
              showClassOverall={showClassOverall && hasClassData}
              showClassBySubject={showClassBySubject && hasClassData}
              animate={animate}
            />
            <div className="sp-dyn-legend">
              <label>
                <input type="checkbox" checked={showOverall} onChange={(e) => setShowOverall(e.target.checked)} /> {t("dyn.legendOverall")}
              </label>
              {hasClassData && (
                <>
                  <label>
                    <input type="checkbox" checked={showClassOverall} onChange={(e) => setShowClassOverall(e.target.checked)} /> {t("dyn.legendClass")}
                  </label>
                  <label>
                    <input type="checkbox" checked={showClassBySubject} onChange={(e) => setShowClassBySubject(e.target.checked)} /> {t("dyn.legendClassBySubject")}
                  </label>
                </>
              )}
              <span>● {t("dyn.legendNazorat")}</span>
              <span>⬤ {t("dyn.legendChorak")}</span>
              {data.missed.length > 0 && <span style={{ color: "var(--danger)" }}>× {t("dyn.legendMissed")}</span>}
            </div>
          </Card>

          <Card>
            <h2 className="h4" style={{ marginBottom: "var(--space-1)" }}>
              {t("dyn.heatmapTitle")}
            </h2>
            <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-3)" }}>
              {t("dyn.heatmapHint")}
            </p>
            <Heatmap points={data.points} />
          </Card>

          <div>
            <h2 className="h4" style={{ marginBottom: "var(--space-3)" }}>
              {t("dyn.subjectsTitle")}
            </h2>
            <div className="sp-dyn-subjects">
              {subjectsForCards.map((s) => (
                <SubjectCard key={s.subject_id} s={s} color={colors.get(s.subject_id) ?? "var(--brand-600)"} values={data.points.filter((p) => p.subject_id === s.subject_id).map((p) => p.percent)} />
              ))}
            </div>
          </div>

          <Card className="stack">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-2)" }}>
              <h2 className="h4">{t("dyn.listTitle")}</h2>
              <select className="sp-input" style={{ width: "auto" }} value={filterSubject} onChange={(e) => setFilterSubject(e.target.value === "" ? "" : Number(e.target.value))} aria-label={t("blocks.subject")}>
                <option value="">{t("dyn.allSubjects")}</option>
                {data.subjects.map((s) => (
                  <option key={s.subject_id} value={s.subject_id}>
                    {s.subject_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="sp-table-scroll">
              <table className="sp-data-table">
                <thead>
                  <tr>
                    <th className="sp-data-table__text">{t("dyn.colExam")}</th>
                    <th className="sp-data-table__text">{t("blocks.subject")}</th>
                    <th>{t("dyn.colDate")}</th>
                    <th>{t("blocks.score")}</th>
                    <th>%</th>
                    <th>{t("dyn.classAvg")}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((p) => (
                    <tr key={`${p.exam_id}-${p.subject_id}`}>
                      <td className="sp-data-table__text">
                        {p.exam_title} {p.exam_type === "chorak" && <Badge status="info">{t("examType.chorakShort")}</Badge>}
                      </td>
                      <td className="sp-data-table__text" style={{ fontWeight: 400 }}>{p.subject_name}</td>
                      <td>{formatDateShortUz(`${p.date}T00:00:00`)}</td>
                      <td>
                        {formatPoints(p.score)}/{formatPoints(p.max_score)}
                        {p.provisional ? " *" : ""}
                      </td>
                      <td style={{ color: toneColor(p.percent, APP), fontWeight: 700 }}>{Math.round(p.percent)}%</td>
                      <td>{p.class_percent === null ? "—" : `${Math.round(p.class_percent)}%`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {provisionalCount > 0 && <p className="caption">* {t("dyn.provisionalNote")}</p>}
          </Card>
        </>
      )}
    </div>
  );
}

function SubjectCard({ s, color, values }: { s: DynamicsSubject; color: string; values: number[] }) {
  const { t } = useLanguage();
  const vsClass = s.class_percent === null ? null : Math.round(s.current_percent - s.class_percent);
  return (
    <Card className="sp-dyn-subject">
      <div className="sp-dyn-subject__row">
        <strong>{s.subject_name}</strong>
        <span className="data-sub">{t("dyn.examsN", { n: s.exams_count })}</span>
      </div>
      <div className="sp-dyn-subject__row">
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 26, fontWeight: 800, color: toneColor(s.current_percent, APP) }}>
          {Math.round(s.current_percent)}%
        </span>
        <MiniSpark values={values} color={color} />
      </div>
      <div className="sp-dyn-subject__row">
        <DeltaChip delta={s.delta} />
        {s.delta !== null && (
          <span className="caption">{t("dyn.fromTo", { from: Math.round(s.baseline_percent), to: Math.round(s.current_percent) })}</span>
        )}
      </div>
      {vsClass !== null && (
        <span className="caption" style={{ color: vsClass >= 0 ? "var(--success)" : "var(--danger)" }}>
          {vsClass >= 0 ? t("dyn.aboveClass", { n: vsClass }) : t("dyn.belowClass", { n: Math.abs(vsClass) })}
        </span>
      )}
    </Card>
  );
}
