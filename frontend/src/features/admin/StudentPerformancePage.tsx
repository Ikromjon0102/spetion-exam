import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getStudentPerformance,
  getStudentSubjectHistory,
  type StudentPerformance,
  type SubjectHistory,
} from "../../api/adminApi";
import { AdminLayout, Badge, Button, Card, Logo, LineChart, ListRow, type BadgeStatus } from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";
import { formatDateUz } from "../../utils/formatDate";

const TREND_KEYS: Record<string, string> = {
  improving: "trend.improving",
  declining: "trend.declining",
  stable: "trend.stable",
};

const TREND_STATUS: Record<string, BadgeStatus> = {
  improving: "success",
  declining: "danger",
  stable: "neutral",
};

function percentTone(percent: number | null): { color: string } {
  if (percent === null) return { color: "var(--ink-muted)" };
  if (percent < 50) return { color: "var(--danger)" };
  if (percent < 70) return { color: "var(--warning)" };
  return { color: "var(--success)" };
}

export default function StudentPerformancePage() {
  const { studentId } = useParams();
  const id = Number(studentId);
  const { t } = useLanguage();
  const [performance, setPerformance] = useState<StudentPerformance | null>(null);
  const [histories, setHistories] = useState<Record<number, SubjectHistory>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getStudentPerformance(id)
      .then(setPerformance)
      .catch(() => setError(t("studentPerformance.loadError")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    performance?.subjects.forEach((s) => {
      getStudentSubjectHistory(id, s.subject_id)
        .then((h) => setHistories((prev) => ({ ...prev, [s.subject_id]: h })))
        .catch(() => undefined);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, performance]);

  const subjects = performance
    ? [...performance.subjects].sort((a, b) => (a.average_percent ?? 0) - (b.average_percent ?? 0))
    : [];

  return (
    <AdminLayout>
      <div className="page">
        <div
          className="print-only"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "var(--space-6)",
            paddingBottom: "var(--space-4)",
            borderBottom: "1.5px solid var(--border)",
          }}
        >
          <Logo tone="red" height={28} />
          <span className="body-sm ink-muted">{formatDateUz(new Date().toISOString())}</span>
        </div>

        <Link
          to="/admin/manage/students"
          className="body-sm no-print"
          style={{ marginBottom: "var(--space-4)", display: "inline-block" }}
        >
          ← {t("studentPerformance.back")}
        </Link>
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: "var(--space-3)",
            marginBottom: "var(--space-2)",
          }}
        >
          <h1 className="h2" style={{ margin: 0 }}>
            {performance?.full_name ?? t("studentPerformance.title")}
          </h1>
          {performance && (
            <Button variant="secondary" size="sm" className="no-print" onClick={() => window.print()}>
              {t("common.print")}
            </Button>
          )}
        </div>
        <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-6)" }}>
          {t("studentPerformance.subtitle")}
        </p>

        {error && (
          <p role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </p>
        )}

        {performance && subjects.length === 0 && (
          <ListRow state="free" title={t("studentPerformance.empty")} />
        )}

        <div className="row-stack">
          {subjects.map((s) => {
            const history = histories[s.subject_id];
            return (
              <Card key={s.subject_id}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                  <div>
                    <h2 className="h4" style={{ marginBottom: "var(--space-1)" }}>
                      {s.subject_name}
                    </h2>
                    <p className="body-sm ink-muted">
                      {s.exams_taken_count} {t("studentPerformance.examsCount")}
                      {s.last_exam_at && ` · ${formatDateUz(s.last_exam_at)}`}
                    </p>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="data-value" style={{ fontSize: 24, ...percentTone(s.average_percent) }}>
                      {s.average_percent !== null ? `${s.average_percent}%` : "—"}
                    </div>
                    {s.trend && (
                      <Badge status={TREND_STATUS[s.trend] ?? "neutral"}>{t(TREND_KEYS[s.trend] ?? s.trend)}</Badge>
                    )}
                  </div>
                </div>
                {history && history.timeline.length > 1 && (
                  <div style={{ marginTop: "var(--space-5)" }}>
                    <LineChart
                      points={history.timeline.map((p) => ({
                        label: formatDateUz(p.date),
                        value: (100 * p.score) / p.max_score,
                      }))}
                    />
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      </div>
    </AdminLayout>
  );
}
