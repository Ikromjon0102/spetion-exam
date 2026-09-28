import { useEffect, useRef, useState } from "react";
import html2canvas from "html2canvas";
import { Link, useParams } from "react-router-dom";
import { getClassDailyResults, type DailyClassResults } from "../../api/adminApi";
import { AdminLayout, Button, EmptyState, Logo } from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";
import { formatDateUz } from "../../utils/formatDate";
import sparkMarkRed from "../../assets/logos/spetion-mark-red.png";

// A4 at 96dpi (CSS px) x2, matching the html2canvas scale below — the
// exported image is always exactly this size regardless of student count
// (a small class gets letterboxed white space, a long roster is scaled
// down to fit), since a shareable/printable result card should be one
// consistent page, not a table that grows without bound.
const A4_WIDTH_PX = 1587;
const A4_HEIGHT_PX = 2245;

// The captured card is styled with hard-coded colors, not CSS variables —
// this image leaves the app (shared to Telegram by the homeroom teacher),
// so it must look the same regardless of the viewer's theme and must not
// depend on html2canvas resolving var(--...) correctly.
const CARD_INK = "#1a1a1a";
const CARD_MUTED = "#6b6b6b";
const CARD_BRAND = "#dd1808";
const CARD_BORDER = "#ececec";
const CARD_ZEBRA = "#fdf5f4";
const CARD_CALLOUT_BG = "#fdf6e3";
const CARD_STAR_BG = "#f5a623";
// Same gold/silver/bronze as RankBadge — duplicated as hex rather than
// reused, since this component's whole point is hardcoded colors (see above).
const CARD_MEDAL: Record<number, string> = { 1: "#f0c419", 2: "#c7cbd1", 3: "#d1904a" };

// Same red/amber/green thresholds used everywhere else percent quality is
// shown (StudentPerformancePage, ExamResultPage) — hardcoded pairs here for
// the same reason as the rest of this file's colors.
function percentPill(percent: number): { bg: string; fg: string } {
  if (percent < 50) return { bg: "#fbe9e7", fg: "#b11306" };
  if (percent < 70) return { bg: "#fdf0e0", fg: "#b36205" };
  return { bg: "#e9f6ee", fg: "#2f9e5b" };
}

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

      // Compose the (variable-height, depends on student count) capture
      // onto a fixed A4 canvas — scaled to fit and centered, never cropped,
      // with white letterboxing on whichever axis has room to spare.
      const a4Canvas = document.createElement("canvas");
      a4Canvas.width = A4_WIDTH_PX;
      a4Canvas.height = A4_HEIGHT_PX;
      const ctx = a4Canvas.getContext("2d");
      if (!ctx) throw new Error("no 2d context");
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, A4_WIDTH_PX, A4_HEIGHT_PX);
      const fitScale = Math.min(A4_WIDTH_PX / canvas.width, A4_HEIGHT_PX / canvas.height);
      const drawWidth = canvas.width * fitScale;
      const drawHeight = canvas.height * fitScale;
      ctx.drawImage(canvas, (A4_WIDTH_PX - drawWidth) / 2, (A4_HEIGHT_PX - drawHeight) / 2, drawWidth, drawHeight);

      const link = document.createElement("a");
      link.download = `${data.class_name}-${data.date}.png`;
      link.href = a4Canvas.toDataURL("image/png");
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

  const topStudent = data && data.students.length > 0 ? data.students[0] : null;
  const totalQuestions = data ? data.exams.reduce((sum, e) => sum + e.question_count, 0) : 0;

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
                position: "relative",
                backgroundColor: "#ffffff",
                color: CARD_INK,
                borderRadius: 12,
                width: "fit-content",
                minWidth: 560,
                border: `1px solid ${CARD_BORDER}`,
                fontFamily: "Inter, system-ui, sans-serif",
                overflow: "hidden",
              }}
            >
              {/* The brand's own mark, tiled at low opacity behind the real
                  content — a plain opacity on this layer (not a filter/blur,
                  which html2canvas doesn't rasterize reliably) so the actual
                  logo never gets redrawn/distorted by hand. */}
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  backgroundImage: `url(${sparkMarkRed})`,
                  backgroundRepeat: "repeat",
                  backgroundSize: "70px 70px",
                  opacity: 0.06,
                }}
              />
              <div style={{ position: "relative" }}>
                <div style={{ height: 8, background: CARD_BRAND }} />

                <div style={{ padding: "28px 32px 8px", textAlign: "center" }}>
                  <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
                    <Logo tone="red" height={30} />
                  </div>
                  <h2 style={{ fontSize: 26, letterSpacing: 1, margin: 0, marginBottom: 4 }}>
                    {t("dailyResults.cardTitle", { className: data.class_name.toUpperCase() })}
                  </h2>
                  <p style={{ fontSize: 14, color: CARD_MUTED, margin: 0, marginBottom: 20 }}>
                    {t("dailyResults.cardSubtitleWithDate", { date: formatDateUz(data.date) })}
                  </p>

                  {topStudent && (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 14,
                        background: CARD_CALLOUT_BG,
                        borderLeft: `4px solid ${CARD_BRAND}`,
                        borderRadius: 8,
                        padding: "14px 18px",
                        marginBottom: 20,
                        textAlign: "left",
                      }}
                    >
                      <span
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          width: 36,
                          height: 36,
                          borderRadius: 999,
                          background: CARD_STAR_BG,
                          flexShrink: 0,
                        }}
                      >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="#ffffff">
                          <path d="M12 2l2.9 6.6 7.1.6-5.4 4.7 1.6 7-6.2-3.9-6.2 3.9 1.6-7L1.9 9.2l7.1-.6z" />
                        </svg>
                      </span>
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: "#b36205", letterSpacing: 0.5 }}>
                          {t("dailyResults.topResult").toUpperCase()}
                        </div>
                        <div style={{ fontSize: 18, fontWeight: 800 }}>
                          {topStudent.full_name} — {topStudent.percent}%
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {data.exams.length > 0 && (
                  <div style={{ padding: "0 32px 20px" }}>
                    <table style={{ borderCollapse: "collapse", fontSize: 13, width: "100%", background: "#ffffff" }}>
                      <thead>
                        <tr style={{ background: CARD_BRAND, color: "#ffffff" }}>
                          <th rowSpan={2} style={{ padding: "8px 10px", fontSize: 12 }}>
                            T/R
                          </th>
                          <th rowSpan={2} style={{ textAlign: "left", padding: "8px 10px", fontSize: 12 }}>
                            {t("dailyResults.studentColumn")}
                          </th>
                          {data.exams.map((exam) => (
                            <th key={exam.exam_id} style={{ padding: "8px 10px", fontSize: 12, whiteSpace: "nowrap" }}>
                              {exam.subject_name}
                            </th>
                          ))}
                          <th style={{ padding: "8px 10px", fontSize: 12 }}>{t("dailyResults.totalColumn")}</th>
                        </tr>
                        <tr style={{ background: CARD_BRAND, color: "rgba(255,255,255,0.75)" }}>
                          {data.exams.map((exam) => (
                            <th key={exam.exam_id} style={{ padding: "0 10px 8px", fontSize: 11, fontWeight: 400 }}>
                              {t("dailyResults.questionCountSuffix", { count: exam.question_count })}
                            </th>
                          ))}
                          <th style={{ padding: "0 10px 8px", fontSize: 11, fontWeight: 400 }}>%</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.students.map((row, rowIndex) => {
                          const pill = percentPill(row.percent);
                          return (
                            <tr
                              key={row.student_id}
                              style={{ background: rowIndex % 2 === 1 ? CARD_ZEBRA : "#ffffff" }}
                            >
                              <td style={{ padding: "8px 10px", textAlign: "center" }}>
                                <span
                                  style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    minWidth: 24,
                                    height: 24,
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
                              <td style={{ padding: "8px 10px", whiteSpace: "nowrap", fontWeight: 600 }}>
                                {row.full_name}
                              </td>
                              {row.scores.map((score, i) => (
                                <td
                                  key={data.exams[i].exam_id}
                                  style={{
                                    padding: "8px 10px",
                                    textAlign: "center",
                                    fontFamily: "'Space Mono', monospace",
                                    color: score === null ? CARD_MUTED : CARD_INK,
                                  }}
                                >
                                  {score === null ? "—" : `${score}/${data.exams[i].question_count}`}
                                </td>
                              ))}
                              <td style={{ padding: "8px 10px", textAlign: "center" }}>
                                <span
                                  style={{
                                    display: "inline-block",
                                    padding: "3px 10px",
                                    borderRadius: 999,
                                    fontSize: 13,
                                    fontWeight: 700,
                                    background: pill.bg,
                                    color: pill.fg,
                                  }}
                                >
                                  {row.percent}%
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                <div
                  style={{
                    padding: "12px 32px",
                    borderTop: `1px solid ${CARD_BORDER}`,
                    textAlign: "center",
                    fontSize: 12,
                    color: CARD_MUTED,
                  }}
                >
                  {t("dailyResults.footerSummary", { students: data.students.length, questions: totalQuestions })}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </AdminLayout>
  );
}
