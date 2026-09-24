export interface BarDatum {
  label: string;
  value: number;
  tone?: "default" | "danger" | "warning" | "success" | "info";
}

const TONE_COLOR: Record<string, string> = {
  default: "var(--brand-600)",
  danger: "var(--danger)",
  warning: "var(--warning)",
  success: "var(--success)",
  info: "var(--info)",
};

/** Minimal inline bar chart — no charting library, matches the design
 * system's flat/geometric look. */
export default function BarChart({ data, height = 160 }: { data: BarDatum[]; height?: number }) {
  if (data.length === 0) return null;
  const max = Math.max(1, ...data.map((d) => d.value));

  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: "var(--space-3)", height, width: "100%" }}>
      {data.map((d, i) => (
        <div
          key={i}
          style={{
            flex: 1,
            minWidth: 0,
            height: "100%",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: "var(--space-1)",
          }}
        >
          <span className="data-value">{d.value}</span>
          <div
            style={{
              width: "100%",
              maxWidth: 44,
              height: Math.max(4, (d.value / max) * (height - 46)),
              background: TONE_COLOR[d.tone ?? "default"],
              borderRadius: "6px 6px 2px 2px",
            }}
          />
          <span
            className="data-eyebrow"
            style={{ textAlign: "center", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", width: "100%" }}
            title={d.label}
          >
            {d.label}
          </span>
        </div>
      ))}
    </div>
  );
}
