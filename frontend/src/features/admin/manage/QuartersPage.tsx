import { useEffect, useState } from "react";
import { getQuarters, saveQuarters, type QuartersInfo } from "../../../api/adminApi";
import { AdminLayout, Badge, Button, Card, Toast } from "../../../components/ui";
import { useLanguage } from "../../../i18n/LanguageContext";
import { errorDetail } from "../../../utils/errorDetail";

// The school's own calendar, for the "standart sanalar" button — the same
// defaults the backend uses until an admin saves different ones.
const DEFAULT_RANGES: Record<number, [string, string]> = {
  1: ["09-01", "11-05"],
  2: ["11-06", "01-11"],
  3: ["01-12", "04-07"],
  4: ["04-08", "07-01"],
};

/** A month-day in the school year that starts in `year` (Sep-Dec are that
 * calendar year, Jan-Aug the next). */
function inSchoolYear(monthDay: string, year: number): string {
  return `${Number(monthDay.slice(0, 2)) >= 9 ? year : year + 1}-${monthDay}`;
}

/** Admin-only: the four chorak date ranges. The exam list's default view is
 * "the current chorak", and an exam belongs to the chorak its start date falls
 * in. Only month and day are stored — the same calendar repeats every year. */
export default function QuartersPage() {
  const { t } = useLanguage();
  const [info, setInfo] = useState<QuartersInfo | null>(null);
  const [draft, setDraft] = useState<Record<number, [string, string]>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function load(next: QuartersInfo) {
    setInfo(next);
    setDraft(Object.fromEntries(next.quarters.map((q) => [q.number, [q.start_date, q.end_date]])));
  }

  useEffect(() => {
    getQuarters()
      .then(load)
      .catch(() => setError(t("quarter.loadError")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function setDate(number: number, which: 0 | 1, value: string) {
    setDraft((prev) => {
      const row: [string, string] = [...prev[number]] as [string, string];
      row[which] = value;
      return { ...prev, [number]: row };
    });
  }

  function useDefaults() {
    if (!info) return;
    setDraft(
      Object.fromEntries(
        Object.entries(DEFAULT_RANGES).map(([n, [s, e]]) => [
          Number(n),
          [inSchoolYear(s, info.school_year_start), inSchoolYear(e, info.school_year_start)],
        ])
      )
    );
  }

  async function handleSave() {
    if (!info) return;
    setError(null);
    if (Object.values(draft).some(([s, e]) => !s || !e)) return setError(t("quarter.needAllDates"));
    setSaving(true);
    try {
      load(
        await saveQuarters(
          Object.entries(draft).map(([n, [s, e]]) => ({ number: Number(n), start_date: s, end_date: e }))
        )
      );
      setMessage(t("quarter.saved"));
    } catch (e) {
      setError(errorDetail(e, t("templates.saveError")));
    } finally {
      setSaving(false);
    }
  }

  const year = info?.school_year_start ?? new Date().getFullYear();
  const min = `${year}-09-01`;
  const max = `${year + 1}-08-31`;

  return (
    <AdminLayout>
      <div className="page" style={{ maxWidth: 720 }}>
        <h1 className="h2" style={{ marginBottom: "var(--space-1)" }}>
          {t("quarter.title")}
        </h1>
        <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-6)" }}>
          {t("quarter.subtitle", { year: `${year}/${String(year + 1).slice(2)}` })}
        </p>

        {error && (
          <p role="alert" style={{ color: "var(--danger)", marginBottom: "var(--space-4)" }}>
            {error}
          </p>
        )}

        {info && (
          <Card className="stack">
            {info.quarters.map((q) => (
              <div key={q.number} className="sp-form-row" style={{ alignItems: "flex-end" }}>
                <div style={{ flex: "0 0 140px", display: "flex", alignItems: "center", gap: "var(--space-2)", minHeight: 40 }}>
                  <strong>{t("chorak.quarterN", { n: q.number })}</strong>
                  {q.number === info.current_number && <Badge status="info">{t("quarter.now")}</Badge>}
                </div>
                <div className="sp-field" style={{ flex: 1 }}>
                  <label className="sp-field__label">{t("quarter.from")}</label>
                  <input
                    className="sp-input"
                    type="date"
                    min={min}
                    max={max}
                    value={draft[q.number]?.[0] ?? ""}
                    onChange={(e) => setDate(q.number, 0, e.target.value)}
                  />
                </div>
                <div className="sp-field" style={{ flex: 1 }}>
                  <label className="sp-field__label">{t("quarter.to")}</label>
                  <input
                    className="sp-input"
                    type="date"
                    min={min}
                    max={max}
                    value={draft[q.number]?.[1] ?? ""}
                    onChange={(e) => setDate(q.number, 1, e.target.value)}
                  />
                </div>
              </div>
            ))}
            <p className="caption">{t("quarter.note")}</p>
            <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
              <Button onClick={handleSave} disabled={saving}>
                {t("common.save")}
              </Button>
              <Button variant="ghost" onClick={useDefaults}>
                {t("quarter.useDefaults")}
              </Button>
            </div>
          </Card>
        )}
      </div>
      {message && <Toast kind="success" text={message} autoDismissMs={3000} onClose={() => setMessage(null)} />}
    </AdminLayout>
  );
}
