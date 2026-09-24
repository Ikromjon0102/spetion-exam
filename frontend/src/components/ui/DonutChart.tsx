export interface DonutSegment {
  label: string;
  value: number;
  color: string;
}

/** Minimal inline donut chart via conic-gradient — no charting library. */
export default function DonutChart({
  segments,
  size = 140,
  thickness = 22,
}: {
  segments: DonutSegment[];
  size?: number;
  thickness?: number;
}) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  let acc = 0;
  const stops = segments
    .filter((s) => s.value > 0)
    .map((s) => {
      const start = (acc / total) * 360;
      acc += s.value;
      const end = (acc / total) * 360;
      return `${s.color} ${start}deg ${end}deg`;
    })
    .join(", ");

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-5)", flexWrap: "wrap" }}>
      <div
        style={{
          width: size,
          height: size,
          borderRadius: "50%",
          flexShrink: 0,
          background: total > 0 ? `conic-gradient(${stops})` : "var(--surface-sunken)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            width: size - thickness * 2,
            height: size - thickness * 2,
            borderRadius: "50%",
            background: "var(--surface-raised)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <span className="data-value">{total}</span>
        </div>
      </div>
      <div className="stack" style={{ gap: "var(--space-2)" }}>
        {segments.map((s) => (
          <div key={s.label} style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <span
              style={{ width: 10, height: 10, borderRadius: "50%", background: s.color, display: "inline-block", flexShrink: 0 }}
            />
            <span className="body-sm">
              {s.label}: {s.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
