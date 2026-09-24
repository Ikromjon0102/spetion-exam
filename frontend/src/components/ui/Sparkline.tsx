interface Props {
  /** Percent values, 0-100, in chronological order. */
  points: number[];
  height?: number;
}

/** Minimal inline trend line — no charting library, matches the rest of
 * the design system (brand color, transparent bg). Not meant for precise
 * reading, just a shape ("is this going up or down"). */
export default function Sparkline({ points, height = 44 }: Props) {
  if (points.length === 0) return null;

  const w = 300;
  const h = 60;
  const padY = 8;
  const n = points.length;
  const clamped = points.map((p) => Math.max(0, Math.min(100, p)));

  const coords = clamped.map((p, i) => {
    const x = n === 1 ? w / 2 : (i / (n - 1)) * w;
    const y = padY + (1 - p / 100) * (h - padY * 2);
    return [x, y] as const;
  });

  const path = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      style={{ width: "100%", height, display: "block" }}
      aria-hidden="true"
    >
      <path d={path} fill="none" stroke="var(--brand-600)" strokeWidth={2} vectorEffect="non-scaling-stroke" />
      {coords.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={i === n - 1 ? 3.5 : 2} fill="var(--brand-600)" />
      ))}
    </svg>
  );
}
