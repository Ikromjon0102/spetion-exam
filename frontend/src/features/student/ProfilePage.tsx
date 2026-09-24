import { useEffect, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { getSubjectHistory, listSubjects, type Subject, type SubjectHistory } from "../../api/studentApi";
import { AppHeader, Badge, Card, ListRow, Sparkline, type BadgeStatus } from "../../components/ui";
import { formatDateUz } from "../../utils/formatDate";
import { useLanguage } from "../../i18n/LanguageContext";

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

export default function ProfilePage() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [histories, setHistories] = useState<Record<number, SubjectHistory>>({});

  useEffect(() => {
    listSubjects().then(setSubjects).catch(() => undefined);
  }, []);

  useEffect(() => {
    subjects.forEach((s) => {
      getSubjectHistory(s.id)
        .then((h) => setHistories((prev) => ({ ...prev, [s.id]: h })))
        .catch(() => undefined);
    });
  }, [subjects]);

  const activeHistories = Object.values(histories).filter((h) => h.exams_taken_count > 0);

  return (
    <>
      <AppHeader />
      <div className="page">
        <h1 className="h2" style={{ marginBottom: "var(--space-1)" }}>
          {user?.full_name}
        </h1>
        <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-8)" }}>
          {t("profile.subtitle")}
        </p>

        {activeHistories.length === 0 && (
          <ListRow state="free" title={t("profile.empty")} subtitle={t("profile.emptySubtitle")} />
        )}

        <div className="stack">
          {activeHistories.map((h) => (
            <Card key={h.subject_id}>
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  marginBottom: "var(--space-4)",
                }}
              >
                <div>
                  <h2 className="h4">{h.subject_name}</h2>
                  <p className="body-sm ink-muted">
                    {h.exams_taken_count} {t("profile.examsCount")} · {t("profile.average")}{" "}
                    {h.average_percent !== null ? `${h.average_percent}%` : "—"}
                  </p>
                </div>
                {h.trend && (
                  <Badge status={TREND_STATUS[h.trend] ?? "neutral"}>{t(TREND_KEYS[h.trend] ?? h.trend)}</Badge>
                )}
              </div>
              {h.timeline.length > 1 && (
                <div style={{ marginBottom: "var(--space-4)" }}>
                  <Sparkline points={h.timeline.map((p) => (100 * p.score) / p.max_score)} />
                </div>
              )}
              <div className="row-stack">
                {h.timeline.map((p) => (
                  <ListRow
                    key={p.exam_id}
                    leading={<span className="data-value">{Math.round((100 * p.score) / p.max_score)}%</span>}
                    title={p.exam_title}
                    subtitle={formatDateUz(p.date)}
                    trailing={
                      <span className="data-value ink-muted">
                        {p.score}/{p.max_score}
                      </span>
                    }
                  />
                ))}
              </div>
            </Card>
          ))}
        </div>
      </div>
    </>
  );
}
