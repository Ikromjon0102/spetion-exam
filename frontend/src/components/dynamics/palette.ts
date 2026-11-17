/** Chart colours. On screen the charts follow the app's theme through CSS
 * variables; the A4 report leaves the app (PDF to a parent), so it uses fixed
 * hex values — it must look the same in light and dark mode and must not depend
 * on the PDF capture resolving var(--...). */
export interface Palette {
  ink: string;
  muted: string;
  faint: string;
  border: string;
  surface: string;
  sunken: string;
  brand: string;
  success: string;
  warning: string;
  danger: string;
  info: string;
}

export const APP: Palette = {
  ink: "var(--ink)",
  muted: "var(--ink-muted)",
  faint: "var(--ink-faint)",
  border: "var(--border)",
  surface: "var(--surface-raised)",
  sunken: "var(--surface-sunken)",
  brand: "var(--brand-600)",
  success: "var(--success)",
  warning: "var(--warning)",
  danger: "var(--danger)",
  info: "var(--info)",
};

export const PAPER: Palette = {
  ink: "#241512",
  muted: "#8a7975",
  faint: "#c4b7b4",
  border: "#ede4e2",
  surface: "#ffffff",
  sunken: "#f5f5f4",
  brand: "#dd1808",
  success: "#2f9e5b",
  warning: "#b36205",
  danger: "#b11306",
  info: "#366fec",
};

/** Same thresholds as the rest of the app: red < 50, amber 50-70, green >= 70. */
export function toneColor(percent: number | null, c: Palette): string {
  if (percent === null) return c.muted;
  if (percent < 50) return c.danger;
  if (percent < 70) return c.warning;
  return c.success;
}

const SUBJECT_COLORS = [
  "#366fec",
  "#2f9e5b",
  "#dd1808",
  "#b36205",
  "#8b5cf6",
  "#0891b2",
  "#db2777",
  "#65a30d",
  "#475569",
  "#ea580c",
];

/** A stable colour per subject (by id order), shared by every chart on a page. */
export function subjectColors(subjectIds: number[]): Map<number, string> {
  const sorted = [...subjectIds].sort((a, b) => a - b);
  return new Map(sorted.map((id, i) => [id, SUBJECT_COLORS[i % SUBJECT_COLORS.length]]));
}

/** Heatmap cell colour: red -> amber -> green with the score. */
export function heatColor(percent: number): string {
  const p = Math.max(0, Math.min(100, percent));
  return `hsl(${Math.round(p * 1.2)} 68% ${Math.round(80 - p * 0.14)}%)`;
}
