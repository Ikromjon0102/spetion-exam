import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type { Dynamics } from "../../api/dynamicsApi";
import { useLanguage } from "../../i18n/LanguageContext";
import { exportPagesPdf, fileSlug } from "../../utils/exportPagesPdf";
import DynamicsReport from "./DynamicsReport";
import DynamicsView from "./DynamicsView";

/** Loads a student's dynamics (for a student or for staff — `load` decides),
 * shows the page, and builds the A4 PDF report on demand. `wrap` puts it inside
 * the right shell (student header or staff sidebar). */
export default function DynamicsPage({
  load,
  wrap,
}: {
  load: (schoolYear?: number) => Promise<Dynamics>;
  wrap: (children: ReactNode) => ReactNode;
}) {
  const { t } = useLanguage();
  const [data, setData] = useState<Dynamics | null>(null);
  const [year, setYear] = useState<number | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    load(year)
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError(t("dyn.loadError"));
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, load]);

  const downloadPdf = useCallback(async () => {
    if (!data) return;
    setExporting(true);
    try {
      // let the (off-screen) report mount and lay out before it is captured
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      const pages = Array.from(hostRef.current?.querySelectorAll<HTMLElement>(".sp-report-page") ?? []);
      await exportPagesPdf(
        pages,
        `ozlashtirish-${fileSlug(data.full_name)}-${data.school_year_start}-${String(data.school_year_start + 1).slice(2)}.pdf`
      );
    } catch {
      setError(t("dyn.pdfError"));
    } finally {
      setExporting(false);
    }
  }, [data, t]);

  return (
    <>
      {wrap(
        <div className="page" style={{ maxWidth: 1100 }}>
          {error && (
            <p role="alert" style={{ color: "var(--danger)", marginBottom: "var(--space-4)" }}>
              {error}
            </p>
          )}
          {!data && !error && <p className="ink-muted">{t("taking.loading")}</p>}
          {data && (
            <DynamicsView data={data} onYearChange={setYear} onDownloadPdf={downloadPdf} exporting={exporting} />
          )}
        </div>
      )}
      {/* only exists while a PDF is being made */}
      {data && exporting && <DynamicsReport ref={hostRef} data={data} />}
    </>
  );
}
