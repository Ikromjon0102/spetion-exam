import { useEffect, useRef, useState } from "react";
import html2canvas from "html2canvas";
import { Link, useParams } from "react-router-dom";
import { getClassDailyResults, type DailyClassResults } from "../../api/adminApi";
import { AdminLayout, Button, EmptyState, Logo } from "../../components/ui";
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
// Same gold/silver/bronze as RankBadge — duplicated as hex rather than
// reused, since this component's whole point is hardcoded colors (see above).
const CARD_MEDAL: Record<number, string> = { 1: "#f0c419", 2: "#c7cbd1", 3: "#d1904a" };

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
    setError(null);
    try {
      const canvas = await html2canvas(captureRef.current, { backgroundColor: "#ffffff", scale: 2, useCORS: true });
      const link = document.createElement("a");
      link.download = `${data.class_name}-${data.date}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
    } catch {
      // Previously silent — a failed capture (e.g. a tainted canvas from a
      // cross-origin resource) just left exporting=false with no feedback,
      // indistinguishable from "the button doesn't do anything".
      setError(t("dailyResults.downloadError"));
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

            {data.exams.length === 0 && <EmptyState icon="inbox" title={t("dailyResults.empty")} />}

            <div
              ref={captureRef}
              style={{
                background: "#ffffff",
                color: CARD_INK,
                padding: 32,
                borderRadius: 12,
                width: "fit-content",
                minWidth: 480,
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

              {data.exams.length > 0 && (
                <table style={{ borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr>
                      <th style={{ padding: "4px 8px" }} />
                      <th style={{ textAlign: "left", padding: "4px 8px", fontSize: 12, color: CARD_MUTED }}>
                        {t("dailyResults.studentColumn")}
                      </th>
                      {data.exams.map((exam) => (
                        <th
                          key={exam.exam_id}
                          style={{
                            textAlign: "right",
                            padding: "4px 8px",
                            fontSize: 12,
                            color: CARD_BRAND,
                            borderLeft: `1px solid ${CARD_BORDER}`,
                            whiteSpace: "nowrap",
                          }}
                        >
                          {exam.subject_name}
                        </th>
                      ))}
                      <th
                        style={{
                          textAlign: "right",
                          padding: "4px 8px",
                          fontSize: 12,
                          fontWeight: 700,
                          borderLeft: `2px solid ${CARD_INK}`,
                        }}
                      >
                        {t("dailyResults.totalColumn")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.students.map((row) => (
                      <tr key={row.student_id} style={{ borderBottom: `1px solid ${CARD_BORDER}` }}>
                        <td style={{ padding: "4px 8px", width: 32 }}>
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              justifyContent: "center",
                              minWidth: 22,
                              height: 22,
                              borderRadius: 999,
                              fontSize: 12,
                              fontWeight: 700,
                              background: CARD_MEDAL[row.rank] ?? "transparent",
                              color: CARD_MEDAL[row.rank] ? "#1a1a1a" : CARD_MUTED,
                            }}
                          >
                            {row.rank}
                          </span>
                        </td>
                        <td style={{ padding: "4px 8px", whiteSpace: "nowrap" }}>{row.full_name}</td>
                        {row.scores.map((score, i) => (
                          <td
                            key={data.exams[i].exam_id}
                            style={{
                              padding: "4px 8px",
                              textAlign: "right",
                              fontFamily: "'Space Mono', monospace",
                              borderLeft: `1px solid ${CARD_BORDER}`,
                              color: score === null ? CARD_MUTED : CARD_INK,
                            }}
                          >
                            {score === null ? "—" : score}
                          </td>
                        ))}
                        <td
                          style={{
                            padding: "4px 8px",
                            textAlign: "right",
                            fontFamily: "'Space Mono', monospace",
                            fontWeight: 700,
                            borderLeft: `2px solid ${CARD_INK}`,
                          }}
                        >
                          {row.total}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </div>
    </AdminLayout>
  );
}
