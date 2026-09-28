import "./rankbadge.css";

// Gold/silver/bronze read fine as-is on both light and dark surfaces (like
// the login screen's blobs) — no per-theme override needed.
const MEDAL: Record<number, { bg: string; fg: string }> = {
  1: { bg: "#f0c419", fg: "#4a3800" },
  2: { bg: "#c7cbd1", fg: "#33363d" },
  3: { bg: "#d1904a", fg: "#3d2410" },
};

export default function RankBadge({ rank }: { rank: number }) {
  const medal = MEDAL[rank];
  return (
    <span className="sp-rank-badge" style={medal ? { background: medal.bg, color: medal.fg } : undefined}>
      {rank}
    </span>
  );
}
