import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createClass, listAdminClasses, listMyAssignments, type ClassOut } from "../../../api/adminApi";
import { useAuth } from "../../../auth/AuthContext";
import { AdminLayout, Badge, Button, Card, ListRow } from "../../../components/ui";
import { useLanguage } from "../../../i18n/LanguageContext";
import { errorDetail } from "../../../utils/errorDetail";

export default function ClassesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [classes, setClasses] = useState<ClassOut[]>([]);
  const [visibleIds, setVisibleIds] = useState<Set<number> | null>(null);
  const [grade, setGrade] = useState("");
  const [label, setLabel] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { t } = useLanguage();
  const navigate = useNavigate();

  async function reload() {
    try {
      setClasses(await listAdminClasses());
    } catch {
      setError(t("adminClasses.loadError"));
    }
  }

  useEffect(() => {
    reload();
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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await createClass({ grade_level: Number(grade), label, display_name: displayName });
      setGrade("");
      setLabel("");
      setDisplayName("");
      await reload();
    } catch (err) {
      setError(errorDetail(err, t("adminClasses.addError")));
    } finally {
      setSubmitting(false);
    }
  }

  const visibleClasses = isAdmin ? classes : classes.filter((c) => visibleIds?.has(c.id));

  return (
    <AdminLayout>
      <div className="page">
        <h1 className="h2" style={{ marginBottom: "var(--space-6)" }}>
          {t("adminClasses.title")}
        </h1>

        {isAdmin && (
          <Card style={{ marginBottom: "var(--space-8)" }}>
            <h2 className="h4" style={{ marginBottom: "var(--space-4)" }}>
              {t("adminClasses.addTitle")}
            </h2>
            <form onSubmit={handleSubmit} className="stack">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-3)" }}>
                <input
                  className="sp-input"
                  type="number"
                  placeholder={t("adminClasses.grade")}
                  value={grade}
                  onChange={(e) => setGrade(e.target.value)}
                  required
                />
                <input
                  className="sp-input"
                  placeholder={t("adminClasses.label")}
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  required
                />
                <input
                  className="sp-input"
                  placeholder={t("adminClasses.displayName")}
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  required
                />
              </div>
              {error && (
                <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                  {error}
                </p>
              )}
              <Button type="submit" disabled={submitting}>
                {t("adminClasses.add")}
              </Button>
            </form>
          </Card>
        )}

        {!isAdmin && visibleClasses.length === 0 && (
          <ListRow state="free" title={t("adminClasses.noneForTeacher")} />
        )}

        <div className="row-stack">
          {visibleClasses.map((c) => (
            <ListRow
              key={c.id}
              chevron
              onClick={() => navigate(`/classes/${c.id}`)}
              title={c.display_name}
              subtitle={`${c.grade_level}-daraja · ${c.label}`}
              trailing={
                c.homeroom_teacher_name ? (
                  <Badge status="info">{c.homeroom_teacher_name}</Badge>
                ) : isAdmin ? (
                  <Badge status="neutral">{t("adminClasses.noHomeroom")}</Badge>
                ) : undefined
              }
            />
          ))}
        </div>
      </div>
    </AdminLayout>
  );
}
