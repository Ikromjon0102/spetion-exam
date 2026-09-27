import { useEffect, useRef, useState } from "react";
import html2canvas from "html2canvas";
import { Link, useParams } from "react-router-dom";
import { getClassDailyResults, type DailyClassResults } from "../../api/adminApi";
import { AdminLayout, Button, Logo } from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";
import { formatDateUz } from "../../utils/formatDate";

// The captured card is styled with hard-coded colors, not CSS variables —
// this image leaves the app (shared to Telegram by the homeroom teacher),
// so it must look the same regardless of the viewer's theme and must not
// depend on html2canvas resolving var(--...) correctly.
const CARD_INK = "#1a1a1a";
const CARD_MUTED = "#6b6b6b";
const CARD_BRAND = "#dd1808";
const CARD_BORDER = "#ececec";

export default function DailyResultsPage() {
  const { classId } = useParams();
  const id = Number(classId);
  const { t } = useLanguage();
  const [data, setData] = useState<DailyClassResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const captureRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getClassDailyResults(id)
      .then(setData)
      .catch(() => setError(t("dailyResults.loadError")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleDownload() {
    if (!captureRef.current || !data) return;
    setExporting(true);
    try {
      const canvas = await html2canvas(captureRef.current, { backgroundColor: "#ffffff", scale: 2 });
      const link = document.createElement("a");
      link.download = `${data.class_name}-${data.date}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
    } finally {
      setExporting(false);
    }
  }

  return (
    <AdminLayout>
      <div className="page">
        <Link to={`/classes/${id}`} className="body-sm" style={{ display: "inline-block", marginBottom: "var(--space-3)" }}>
          &larr; {t("classDetail.backToClasses")}
        </Link>
        <h1 className="h2" style={{ marginBottom: "var(--space-1)" }}>
          {t("dailyResults.title")}
        </h1>
        <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-6)" }}>
          {t("dailyResults.subtitle")}
        </p>

        {error && (
          <p role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </p>
        )}

        {data && (
          <>
            <div style={{ marginBottom: "var(--space-5)" }}>
              <Button onClick={handleDownload} disabled={exporting || data.exams.length === 0}>
                {exporting ? t("dailyResults.exporting") : t("dailyResults.download")}
              </Button>
            </div>

            {data.exams.length === 0 && <p className="ink-muted">{t("dailyResults.empty")}</p>}

            <div
              ref={captureRef}
              style={{
                background: "#ffffff",
                color: CARD_INK,
                padding: 32,
                borderRadius: 12,
                maxWidth: 640,
                border: `1px solid ${CARD_BORDER}`,
                fontFamily: "Inter, system-ui, sans-serif",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
                <Logo tone="red" height={30} />
                <span style={{ fontFamily: "'Space Mono', monospace", fontSize: 13, color: CARD_MUTED }}>
                  {formatDateUz(data.date)}
                </span>
              </div>
              <h2 style={{ fontSize: 20, margin: 0, marginBottom: 4 }}>{data.class_name}</h2>
              <p style={{ fontSize: 13, color: CARD_MUTED, margin: 0, marginBottom: 20 }}>
                {t("dailyResults.cardSubtitle")}
              </p>

              {data.exams.map((exam) => (
                <div key={exam.exam_id} style={{ marginBottom: 20 }}>
                  <h3 style={{ fontSize: 15, margin: 0, marginBottom: 8, color: CARD_BRAND }}>
                    {exam.subject_name} — {exam.exam_title}
                  </h3>
                  {exam.rankings.length === 0 ? (
                    <p style={{ fontSize: 13, color: CARD_MUTED, margin: 0 }}>{t("dailyResults.noRankingYet")}</p>
                  ) : (
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                      <tbody>
                        {exam.rankings.map((r) => (
                          <tr key={r.student_id} style={{ borderBottom: `1px solid ${CARD_BORDER}` }}>
                            <td style={{ padding: "4px 8px", width: 32, color: CARD_MUTED }}>#{r.rank_in_class}</td>
                            <td style={{ padding: "4px 8px" }}>{r.full_name}</td>
                            <td
                              style={{
                                padding: "4px 8px",
                                textAlign: "right",
                                fontFamily: "'Space Mono', monospace",
                              }}
                            >
                              {r.score}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </AdminLayout>
  );
}
