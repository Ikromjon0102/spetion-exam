/** The dynamics page's charts. Dependency-free SVG/HTML like the rest of the
 * app's charts (LineChart, DonutChart). Every chart takes `paper`: on screen
 * they use the app theme (CSS variables), in the A4 PDF fixed colours and no
 * animation (see palette.ts). */
import { useEffect, useMemo, useState } from "react";
import type { DynamicsMissed, DynamicsPoint, DynamicsQuarter, DynamicsSubject } from "../../api/dynamicsApi";
import { useLanguage } from "../../i18n/LanguageContext";
import { formatPoints } from "../../utils/formatPoints";
import { APP, PAPER, heatColor, toneColor, type Palette } from "./palette";
import { useCountUp } from "./useMotion";

const palette = (paper?: boolean): Palette => (paper ? PAPER : APP);

function shortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${Number(d)}.${m}`;
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

// ---------------------------------------------------------------- ring ----

interface RingProps {
  value: number | null;
  size?: number;
  paper?: boolean;
  animate?: boolean;
}

/** The overall level as a ring that fills up while the number counts up. */
export function Ring({ value, size = 150, paper, animate = true }: RingProps) {
  const c = palette(paper);
  const stroke = Math.round(size * 0.09);
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const shown = useCountUp(value, animate);
  const [mounted, setMounted] = useState(!animate);
  useEffect(() => {
    if (animate) requestAnimationFrame(() => setMounted(true));
  }, [animate]);
  const fraction = value === null ? 0 : Math.max(0, Math.min(100, value)) / 100;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={value === null ? "—" : `${Math.round(value)}%`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={c.sunken} strokeWidth={stroke} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={toneColor(value, c)}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={mounted ? circumference * (1 - fraction) : circumference}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={animate ? { transition: "stroke-dashoffset 1.1s cubic-bezier(.2,.8,.2,1)" } : undefined}
      />
      <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central" fill={c.ink} fontSize={size * 0.27} fontWeight={800}>
        {shown === null ? "—" : `${Math.round(shown)}%`}
      </text>
    </svg>
  );
}

// --------------------------------------------------------------- radar ----

interface RadarProps {
  subjects: DynamicsSubject[];
  /** 0 = the start of the year, 1 = now; the filled shape morphs between them */
  t: number;
  paper?: boolean;
  size?: number;
}

/** Subjects as spokes: the dashed outline is where the year started, the filled
 * shape is where the slider is (now, at the right end). */
export function Radar({ subjects, t, paper, size = 420 }: RadarProps) {
  const { t: tr } = useLanguage();
  const c = palette(paper);
  const n = subjects.length;
  const cx = size / 2;
  const cy = size / 2;
  const R = size * 0.31;
  const point = (i: number, value: number) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n;
    const radius = (R * Math.max(0, Math.min(100, value))) / 100;
    return [cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)] as const;
  };
  const polygon = (values: number[]) => values.map((v, i) => point(i, v).join(",")).join(" ");
  const baseline = subjects.map((s) => s.baseline_percent);
  const shown = subjects.map((s) => s.baseline_percent + (s.current_percent - s.baseline_percent) * t);
  return (
    <svg viewBox={`0 0 ${size} ${size}`} style={{ width: "100%", maxWidth: size, display: "block", margin: "0 auto" }} role="img">
      {[25, 50, 75, 100].map((ring) => (
        <polygon key={ring} points={polygon(subjects.map(() => ring))} fill="none" stroke={c.border} strokeWidth={1} />
      ))}
      {subjects.map((s, i) => {
        const [x, y] = point(i, 100);
        const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n;
        const lx = cx + (R + 16) * Math.cos(angle);
        const ly = cy + (R + 16) * Math.sin(angle);
        const cos = Math.cos(angle);
        return (
          <g key={s.subject_id}>
            <line x1={cx} y1={cy} x2={x} y2={y} stroke={c.border} strokeWidth={1} />
            <text
              x={lx}
              y={ly}
              textAnchor={cos > 0.3 ? "start" : cos < -0.3 ? "end" : "middle"}
              dominantBaseline="central"
              fill={c.ink}
              fontSize={size * 0.032}
              fontWeight={600}
            >
              {truncate(s.subject_name, 13)}
            </text>
          </g>
        );
      })}
      <polygon points={polygon(baseline)} fill="none" stroke={c.muted} strokeWidth={1.5} strokeDasharray="5 4" />
      <polygon points={polygon(shown)} fill={c.brand} fillOpacity={0.16} stroke={c.brand} strokeWidth={2.2} strokeLinejoin="round" />
      {shown.map((v, i) => {
        const [x, y] = point(i, v);
        return (
          <circle key={subjects[i].subject_id} cx={x} cy={y} r={4} fill={c.brand}>
            <title>
              {subjects[i].subject_name}: {tr("dyn.radarTip", { from: Math.round(subjects[i].baseline_percent), to: Math.round(subjects[i].current_percent) })}
            </title>
          </circle>
        );
      })}
    </svg>
  );
}

// ------------------------------------------------------------ timeline ----

interface TimelineProps {
  points: DynamicsPoint[];
  missed: DynamicsMissed[];
  quarters: DynamicsQuarter[];
  schoolYearStart: number;
  colors: Map<number, string>;
  visible: Set<number>;
  showOverall: boolean;
  showClassOverall: boolean;
  showClassBySubject: boolean;
  paper?: boolean;
  animate?: boolean;
}

const DAY = 86_400_000;
const ms = (iso: string) => Date.parse(`${iso}T00:00:00Z`);

function movingAverage(values: number[], window = 3): number[] {
  return values.map((_, i) => {
    const slice = values.slice(Math.max(0, i - window + 1), i + 1);
    return slice.reduce((a, b) => a + b, 0) / slice.length;
  });
}

/** Every graded exam in time order: one line per subject, the school's chorak
 * as shaded bands, chorak exams as big dots, the class average dashed. */
export function Timeline({
  points,
  missed,
  quarters,
  schoolYearStart,
  colors,
  visible,
  showOverall,
  showClassOverall,
  showClassBySubject,
  paper,
  animate = true,
}: TimelineProps) {
  const { t } = useLanguage();
  const c = palette(paper);
  const W = 900;
  const H = 380;
  const m = { l: 40, r: 14, t: 30, b: 44 };
  const pw = W - m.l - m.r;
  const ph = H - m.t - m.b;

  const dates = [...points.map((p) => p.date), ...missed.map((x) => x.date)];
  const xmin = Date.UTC(schoolYearStart, 8, 1);
  const lastData = dates.length ? Math.max(...dates.map(ms)) : xmin + 30 * DAY;
  const today = Date.now();
  const inThisYear = today >= xmin && today < Date.UTC(schoolYearStart + 1, 8, 1);
  const xmax = Math.max(lastData, inThisYear ? today : 0) + 7 * DAY;
  const x = (iso: string | number) => m.l + ((typeof iso === "number" ? iso : ms(iso)) - xmin) / (xmax - xmin) * pw;
  const y = (v: number) => m.t + (1 - Math.max(0, Math.min(100, v)) / 100) * ph;

  const bySubject = useMemo(() => {
    const map = new Map<number, DynamicsPoint[]>();
    for (const p of points) map.set(p.subject_id, [...(map.get(p.subject_id) ?? []), p]);
    return map;
  }, [points]);
  const sorted = useMemo(() => [...points].sort((a, b) => a.date.localeCompare(b.date) || a.exam_id - b.exam_id), [points]);
  const overall = useMemo(() => {
    const avg = movingAverage(sorted.map((p) => p.percent));
    return sorted.map((p, i) => ({ date: p.date, value: avg[i] }));
  }, [sorted]);
  const classOverall = useMemo(() => {
    const withClass = sorted.filter((p) => p.class_percent !== null);
    const avg = movingAverage(withClass.map((p) => p.class_percent as number));
    return withClass.map((p, i) => ({ date: p.date, value: avg[i] }));
  }, [sorted]);

  const path = (pts: { date: string; value: number }[]) =>
    pts.map((p, i) => `${i === 0 ? "M" : "L"}${x(p.date).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");
  const lineClass = animate ? "sp-dyn-draw" : undefined;

  // month ticks
  const ticks: { label: string; at: number }[] = [];
  for (let d = new Date(xmin); d.getTime() <= xmax; d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1))) {
    ticks.push({ label: t(`month.${d.getUTCMonth() + 1}`), at: d.getTime() });
  }

  // chorak bands: each runs until the next one starts (the last to the year end)
  const bands = quarters.map((q, i) => {
    const start = i === 0 ? xmin : ms(q.start_date);
    const end = i < quarters.length - 1 ? ms(quarters[i + 1].start_date) : Date.UTC(schoolYearStart + 1, 8, 1);
    return { number: q.number, from: Math.max(start, xmin), to: Math.min(end, xmax) };
  });

  const tip = (p: DynamicsPoint) =>
    `${p.subject_name} · ${p.exam_title} · ${shortDate(p.date)} · ${formatPoints(p.score)}/${formatPoints(p.max_score)} (${Math.round(p.percent)}%)` +
    (p.class_percent !== null ? ` · ${t("dyn.classAvg")}: ${Math.round(p.class_percent)}%` : "") +
    (p.provisional ? ` · ${t("dyn.provisional")}` : "");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", display: "block" }} role="img">
      {bands.map(
        (b) =>
          b.to > b.from && (
            <g key={b.number}>
              <rect x={x(b.from)} y={m.t} width={x(b.to) - x(b.from)} height={ph} fill={c.sunken} opacity={b.number % 2 === 1 ? 0.9 : 0.35} />
              <text x={(x(b.from) + x(b.to)) / 2} y={m.t - 10} textAnchor="middle" fill={c.muted} fontSize={12} fontWeight={700}>
                {t("chorak.quarterN", { n: b.number })}
              </text>
            </g>
          )
      )}
      {[0, 25, 50, 75, 100].map((g) => (
        <g key={g}>
          <line x1={m.l} y1={y(g)} x2={W - m.r} y2={y(g)} stroke={c.border} strokeWidth={1} />
          <text x={m.l - 6} y={y(g)} textAnchor="end" dominantBaseline="central" fill={c.faint} fontSize={11}>
            {g}
          </text>
        </g>
      ))}
      {[50, 70].map((g) => (
        <line key={g} x1={m.l} y1={y(g)} x2={W - m.r} y2={y(g)} stroke={g === 50 ? c.danger : c.success} strokeWidth={1} strokeDasharray="2 5" opacity={0.45} />
      ))}
      {ticks.map((tick) => (
        <text key={tick.at} x={x(tick.at)} y={H - m.b + 18} textAnchor="start" fill={c.muted} fontSize={11}>
          {tick.label}
        </text>
      ))}

      {showClassBySubject &&
        [...bySubject.entries()]
          .filter(([id]) => visible.has(id))
          .map(([id, pts]) => {
            const withClass = pts.filter((p) => p.class_percent !== null).map((p) => ({ date: p.date, value: p.class_percent as number }));
            return withClass.length > 1 ? (
              <path key={`cl-${id}`} d={path(withClass)} fill="none" stroke={colors.get(id)} strokeWidth={1.5} strokeDasharray="4 4" opacity={0.6} />
            ) : null;
          })}

      {[...bySubject.entries()]
        .filter(([id]) => visible.has(id))
        .map(([id, pts]) => {
          const color = colors.get(id) ?? c.brand;
          return (
            <g key={id}>
              {pts.length > 1 && (
                <path d={path(pts.map((p) => ({ date: p.date, value: p.percent })))} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" pathLength={1} className={lineClass} opacity={showOverall ? 0.75 : 1} />
              )}
              {pts.map((p) => {
                const big = p.exam_type === "chorak";
                return (
                  <g key={`${p.exam_id}-${p.subject_id}`}>
                    <circle cx={x(p.date)} cy={y(p.percent)} r={big ? 7 : 4} fill={p.provisional ? c.surface : color} stroke={color} strokeWidth={p.provisional ? 2 : 0}>
                      <title>{tip(p)}</title>
                    </circle>
                    {big && !p.provisional && <circle cx={x(p.date)} cy={y(p.percent)} r={3} fill={c.surface} pointerEvents="none" />}
                  </g>
                );
              })}
            </g>
          );
        })}

      {showClassOverall && classOverall.length > 1 && (
        <path d={path(classOverall)} fill="none" stroke={c.muted} strokeWidth={2.2} strokeDasharray="7 5" pathLength={1} className={lineClass} />
      )}
      {showOverall && overall.length > 1 && (
        <path d={path(overall)} fill="none" stroke={c.ink} strokeWidth={3.4} strokeLinejoin="round" strokeLinecap="round" pathLength={1} className={lineClass} />
      )}

      {missed.map((miss) => (
        <text key={miss.exam_id} x={x(miss.date)} y={H - m.b - 6} textAnchor="middle" fill={c.danger} fontSize={14} fontWeight={700} opacity={0.8}>
          ×
          <title>
            {t("dyn.missedTip")}: {miss.exam_title} · {shortDate(miss.date)}
          </title>
        </text>
      ))}
    </svg>
  );
}

// -------------------------------------------------------- quarter bars ----

/** Chorak by chorak: the average of everything sat in it, and the change from
 * the chorak before. */
export function QuarterBars({ quarters, showRank, paper, animate = true }: { quarters: DynamicsQuarter[]; showRank: boolean; paper?: boolean; animate?: boolean }) {
  const { t } = useLanguage();
  const c = palette(paper);
  const [mounted, setMounted] = useState(!animate);
  useEffect(() => {
    if (animate) requestAnimationFrame(() => setMounted(true));
  }, [animate]);
  let previous: number | null = null;
  const cols = quarters.map((q) => {
    const delta = q.percent !== null && previous !== null ? q.percent - previous : null;
    if (q.percent !== null) previous = q.percent;
    return { q, delta };
  });
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, alignItems: "end" }}>
      {cols.map(({ q, delta }) => {
        const tone = toneColor(q.percent, c);
        return (
          <div key={q.number} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, minWidth: 0 }}>
            <div style={{ fontWeight: 800, fontSize: 15, color: q.percent === null ? c.faint : tone, minHeight: 20 }}>
              {q.percent === null ? "—" : `${Math.round(q.percent)}%`}
            </div>
            {delta !== null && (
              <div style={{ fontSize: 11, fontWeight: 700, color: delta >= 0 ? c.success : c.danger }}>
                {delta >= 0 ? "▲ +" : "▼ "}
                {Math.round(delta)}
              </div>
            )}
            <div style={{ width: "100%", height: 130, background: c.sunken, borderRadius: 10, display: "flex", alignItems: "flex-end", overflow: "hidden" }}>
              <div
                style={{
                  width: "100%",
                  height: mounted ? `${q.percent ?? 0}%` : "0%",
                  background: tone,
                  borderRadius: "10px 10px 0 0",
                  transition: animate ? "height 1s cubic-bezier(.2,.8,.2,1)" : undefined,
                }}
              />
            </div>
            <div style={{ fontWeight: 700, fontSize: 13, color: c.ink }}>{t("chorak.quarterN", { n: q.number })}</div>
            <div style={{ fontSize: 11, color: c.muted, textAlign: "center" }}>
              {shortDate(q.start_date)}–{shortDate(q.end_date)}
              <br />
              {q.exams_count > 0 ? t("dyn.examsN", { n: q.exams_count }) : t("dyn.noExamsYet")}
            </div>
            {showRank && q.rank !== null && (
              <div style={{ fontSize: 11, fontWeight: 700, color: c.info }}>
                {t("dyn.rankIn", { rank: q.rank, of: q.rank_of ?? 0 })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------- heatmap ----

/** Subjects x months, each cell the month's average in that subject. */
export function Heatmap({ points, paper }: { points: DynamicsPoint[]; paper?: boolean }) {
  const { t } = useLanguage();
  const c = palette(paper);
  const grid = useMemo(() => {
    const months = [...new Set(points.map((p) => p.date.slice(0, 7)))].sort();
    // fill the months in between, so a quiet month shows up as an empty cell
    const span: string[] = [];
    if (months.length) {
      let [y, m] = months[0].split("-").map(Number);
      const [ey, em] = months[months.length - 1].split("-").map(Number);
      while (y < ey || (y === ey && m <= em)) {
        span.push(`${y}-${String(m).padStart(2, "0")}`);
        m += 1;
        if (m > 12) {
          m = 1;
          y += 1;
        }
      }
    }
    const subjects = new Map<number, string>();
    points.forEach((p) => subjects.set(p.subject_id, p.subject_name));
    const cell = new Map<string, number[]>();
    points.forEach((p) => {
      const key = `${p.subject_id}|${p.date.slice(0, 7)}`;
      cell.set(key, [...(cell.get(key) ?? []), p.percent]);
    });
    return { months: span, subjects: [...subjects.entries()].sort((a, b) => a[1].localeCompare(b[1])), cell };
  }, [points]);
  if (grid.months.length === 0) return null;
  return (
    <div style={{ display: "grid", gridTemplateColumns: `minmax(90px, 130px) repeat(${grid.months.length}, minmax(34px, 1fr))`, gap: 4 }}>
      <div />
      {grid.months.map((ym) => (
        <div key={ym} style={{ fontSize: 11, color: c.muted, textAlign: "center", fontWeight: 700 }}>
          {t(`month.${Number(ym.slice(5))}`)}
        </div>
      ))}
      {grid.subjects.map(([id, name]) => (
        <HeatRow key={id} name={name} id={id} months={grid.months} cell={grid.cell} c={c} />
      ))}
    </div>
  );
}

function HeatRow({ name, id, months, cell, c }: { name: string; id: number; months: string[]; cell: Map<string, number[]>; c: Palette }) {
  return (
    <>
      <div style={{ fontSize: 12, fontWeight: 600, color: c.ink, alignSelf: "center", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={name}>
        {name}
      </div>
      {months.map((ym) => {
        const values = cell.get(`${id}|${ym}`);
        if (!values) return <div key={ym} style={{ height: 30, borderRadius: 6, border: `1px dashed ${c.border}` }} />;
        const avg = values.reduce((a, b) => a + b, 0) / values.length;
        return (
          <div
            key={ym}
            title={`${name} · ${Math.round(avg)}% (${values.length})`}
            style={{ height: 30, borderRadius: 6, background: heatColor(avg), color: "#241512", fontSize: 11, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center" }}
          >
            {Math.round(avg)}
          </div>
        );
      })}
    </>
  );
}

// --------------------------------------------------------------- spark ----

/** A small trend line for a subject card. */
export function MiniSpark({ values, color, width = 110, height = 34 }: { values: number[]; color: string; width?: number; height?: number }) {
  if (values.length < 2) return null;
  const pad = 3;
  const coords = values.map((v, i) => [pad + (i / (values.length - 1)) * (width - pad * 2), pad + (1 - Math.max(0, Math.min(100, v)) / 100) * (height - pad * 2)] as const);
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <path d={coords.map(([px, py], i) => `${i === 0 ? "M" : "L"}${px.toFixed(1)},${py.toFixed(1)}`).join(" ")} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
      <circle cx={coords[coords.length - 1][0]} cy={coords[coords.length - 1][1]} r={3} fill={color} />
    </svg>
  );
}
