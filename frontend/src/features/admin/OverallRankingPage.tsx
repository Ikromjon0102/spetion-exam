import { useEffect, useState } from "react";
import {
  getClassOverallRanking,
  getGradeOverallRanking,
  getSchoolOverallRanking,
  listAdminClasses,
  listMyAssignments,
  type ClassOut,
  type OverallRanking,
} from "../../api/adminApi";
import { useAuth } from "../../auth/AuthContext";
import { AdminLayout, Badge, Button, ListRow } from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";

type Scope = "class" | "grade" | "school";

export default function OverallRankingPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const { t } = useLanguage();

  const [classes, setClasses] = useState<ClassOut[]>([]);
  const [visibleIds, setVisibleIds] = useState<Set<number> | null>(null);
  const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
  const [selectedGrade, setSelectedGrade] = useState<number | null>(null);
  const [scope, setScope] = useState<Scope>("class");
  const [ranking, setRanking] = useState<OverallRanking | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAdminClasses().then(setClasses).catch(() => undefined);
    if (!isAdmin && user) {
      const ids = new Set(user.homeroom_class_ids);
      listMyAssignments()
        .then((rows) => {
          rows.forEach((r) => ids.add(r.class_id));
          setVisibleIds(new Set(ids));
        })
        .catch(() => setVisibleIds(new Set(ids)));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  const visibleClasses = isAdmin ? classes : classes.filter((c) => visibleIds?.has(c.id));
  const grades = Array.from(new Set(classes.map((c) => c.grade_level))).sort((a, b) => a - b);

  useEffect(() => {
    if (selectedClassId === null && visibleClasses.length > 0) {
      setSelectedClassId(visibleClasses[0].id);
    }
  }, [visibleClasses, selectedClassId]);

  useEffect(() => {
    if (selectedGrade === null && grades.length > 0) {
      setSelectedGrade(grades[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [grades.join(",")]);

  useEffect(() => {
    setError(null);
    if (scope === "school") {
      getSchoolOverallRanking()
        .then(setRanking)
        .catch(() => setError(t("overallRanking.loadError")));
      return;
    }
    if (scope === "grade") {
      if (selectedGrade === null) return;
      getGradeOverallRanking(selectedGrade)
        .then(setRanking)
        .catch(() => setError(t("overallRanking.loadError")));
      return;
    }
    if (selectedClassId === null) return;
    getClassOverallRanking(selectedClassId)
      .then(setRanking)
      .catch(() => setError(t("overallRanking.loadError")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, selectedClassId, selectedGrade]);

  return (
    <AdminLayout>
      <div className="page">
        <h1 className="h2" style={{ marginBottom: "var(--space-2)" }}>
          {t("overallRanking.title")}
        </h1>
        <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-6)" }}>
          {t("overallRanking.subtitle")}
        </p>

        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", marginBottom: "var(--space-6)" }}>
          {isAdmin && (
            <div style={{ display: "flex", gap: "var(--space-2)" }}>
              <Button variant={scope === "class" ? "secondary" : "ghost"} onClick={() => setScope("class")}>
                {t("overallRanking.byClass")}
              </Button>
              <Button variant={scope === "grade" ? "secondary" : "ghost"} onClick={() => setScope("grade")}>
                {t("overallRanking.byGrade")}
              </Button>
              <Button variant={scope === "school" ? "secondary" : "ghost"} onClick={() => setScope("school")}>
                {t("overallRanking.bySchool")}
              </Button>
            </div>
          )}

          {scope === "class" && (
            <select
              className="sp-input"
              style={{ maxWidth: 260 }}
              value={selectedClassId ?? ""}
              onChange={(e) => setSelectedClassId(Number(e.target.value))}
            >
              {visibleClasses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.display_name}
                </option>
              ))}
            </select>
          )}

          {scope === "grade" && (
            <select
              className="sp-input"
              style={{ maxWidth: 260 }}
              value={selectedGrade ?? ""}
              onChange={(e) => setSelectedGrade(Number(e.target.value))}
            >
              {grades.map((g) => (
                <option key={g} value={g}>
                  {g}-{t("overallRanking.gradeSuffix")}
                </option>
              ))}
            </select>
          )}
        </div>

        {error && (
          <p role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </p>
        )}

        {!error && ranking && ranking.rankings.length === 0 && (
          <ListRow state="free" title={t("overallRanking.empty")} />
        )}

        {ranking && ranking.rankings.length > 0 && (
          <div className="row-stack">
            {ranking.rankings.map((r) => (
              <ListRow
                key={r.student_id}
                leading={<span className="data-value">#{r.rank}</span>}
                title={r.full_name}
                subtitle={scope !== "class" ? r.class_name : undefined}
                trailing={
                  <>
                    <span className="data-value">{r.average_percent}%</span>
                    <Badge status="neutral">
                      {r.exams_taken_count} {t("overallRanking.examsCount")}
                    </Badge>
                  </>
                }
              />
            ))}
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
