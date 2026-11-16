/** Scores as people write them: 93, 83.7, 10.5 — never 93.0 or the float
 * noise (83.70000000000002) that decimal block weights produce when summed. */
export function formatPoints(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return String(Math.round(value * 100) / 100);
}
