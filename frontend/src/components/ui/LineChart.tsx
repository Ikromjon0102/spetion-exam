export interface LinePoint {
  label: string;
  value: number;
}

const GRID_LINES = [0, 25, 50, 75, 100];

/** A full-size trend line (as opposed to Sparkline's bare inline shape) —
 * gridlines, per-point value labels, and x-axis labels. Still no charting
 * library, matches the rest of this design system's flat/geometric look.
 * Values are assumed to be percents (0-100); pass a subject's exam-by-exam
 * score history to show real progress over time, not just up/down. */
export default function LineChart({ points, height = 220 }: { points: LinePoint[]; height?: number }) {
  if (points.length === 0) return null;

  const w = 600;
  const padTop = 24;
  const padBottom = 36;
  const padX = 8;
  const plotH = height - padTop - padBottom;
  const n = points.length;
  const clamped = points.map((p) => Math.max(0, Math.min(100, p.value)));

  const coords = clamped.map((v, i) => {
    const x = n === 1 ? w / 2 : padX + (i / (n - 1)) * (w - padX * 2);
    const y = padTop + (1 - v / 100) * plotH;
    return [x, y] as const;
  });

  const linePath = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L${coords[coords.length - 1][0].toFixed(1)},${(padTop + plotH).toFixed(1)} L${coords[0][0].toFixed(1)},${(padTop + plotH).toFixed(1)} Z`;

  return (
    <svg viewBox={`0 0 ${w} ${height}`} style={{ width: "100%", height, display: "block" }} role="img">
      {GRID_LINES.map((g) => {
        const y = padTop + (1 - g / 100) * plotH;
        return (
          <g key={g}>
            <line x1={padX} y1={y} x2={w - padX} y2={y} stroke="var(--border)" strokeWidth={1} />
            <text x={0} y={y - 3} className="data-eyebrow" fill="var(--ink-faint)" fontSize={10}>
              {g}%
            </text>
          </g>
        );
      })}

      <path d={areaPath} fill="var(--brand-600)" opacity={0.08} stroke="none" />
      <path d={linePath} fill="none" stroke="var(--brand-600)" strokeWidth={2} vectorEffect="non-scaling-stroke" />

      {coords.map(([x, y], i) => (
        <g key={i}>
          <circle cx={x} cy={y} r={i === n - 1 ? 4.5 : 3} fill="var(--brand-600)" />
          <text
            x={x}
            y={y - 10}
            textAnchor="middle"
            className="data-value"
            fill="var(--ink)"
            fontSize={11}
          >
            {Math.round(clamped[i])}%
          </text>
          <text
            x={x}
            y={height - 12}
            textAnchor="middle"
            className="data-eyebrow"
            fill="var(--ink-muted)"
            fontSize={9}
          >
            {points[i].label.length > 12 ? `${points[i].label.slice(0, 11)}…` : points[i].label}
          </text>
        </g>
      ))}
    </svg>
  );
}
