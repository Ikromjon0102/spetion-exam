import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createClass, listAdminClasses, listMyAssignments, type ClassOut } from "../../../api/adminApi";
import { useAuth } from "../../../auth/AuthContext";
import { AdminLayout, Badge, Button, EmptyState, ListRow, Modal } from "../../../components/ui";
import { useLanguage } from "../../../i18n/LanguageContext";
import { errorDetail } from "../../../utils/errorDetail";

export default function ClassesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [classes, setClasses] = useState<ClassOut[]>([]);
  const [visibleIds, setVisibleIds] = useState<Set<number> | null>(null);
  const [search, setSearch] = useState("");
  const [addOpen, setAddOpen] = useState(false);
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
      setAddOpen(false);
      await reload();
    } catch (err) {
      setError(errorDetail(err, t("adminClasses.addError")));
    } finally {
      setSubmitting(false);
    }
  }

  const visibleClasses = isAdmin ? classes : classes.filter((c) => visibleIds?.has(c.id));
  const filteredClasses = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return visibleClasses;
    return visibleClasses.filter(
      (c) => c.display_name.toLowerCase().includes(q) || c.label.toLowerCase().includes(q)
    );
  }, [visibleClasses, search]);

  return (
    <AdminLayout>
      <div className="page">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "var(--space-3)",
            marginBottom: "var(--space-6)",
          }}
        >
          <h1 className="h2" style={{ margin: 0 }}>
            {t("adminClasses.title")}
          </h1>
          {isAdmin && (
            <Button variant="secondary" size="sm" onClick={() => setAddOpen(true)}>
              + {t("adminClasses.addTitle")}
            </Button>
          )}
        </div>

        <input
          className="sp-input"
          placeholder={t("common.searchPlaceholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 320, marginBottom: "var(--space-6)" }}
        />

        {!isAdmin && visibleClasses.length === 0 && (
          <ListRow state="free" title={t("adminClasses.noneForTeacher")} />
        )}
        {visibleClasses.length > 0 && filteredClasses.length === 0 && (
          <EmptyState icon="search" title={t("common.noSearchResults")} />
        )}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
            gap: "var(--space-3)",
          }}
        >
          {filteredClasses.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => navigate(`/classes/${c.id}`)}
              className="sp-card"
              style={{
                textAlign: "left",
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-2)",
                padding: "var(--space-4)",
                // A native <button> doesn't inherit text color the way a
                // <div> does (browser default form-control color wins
                // otherwise) — same bug already fixed on StatCard.
                color: "inherit",
              }}
            >
              <div className="h5" style={{ margin: 0 }}>
                {c.display_name}
              </div>
              <div className="body-sm ink-muted">
                {c.grade_level}-daraja · {c.label}
              </div>
              {c.homeroom_teacher_name ? (
                <Badge status="info">{c.homeroom_teacher_name}</Badge>
              ) : isAdmin ? (
                <Badge status="neutral">{t("adminClasses.noHomeroom")}</Badge>
              ) : null}
            </button>
          ))}
        </div>
      </div>

      <Modal open={addOpen} onClose={() => setAddOpen(false)} title={t("adminClasses.addTitle")}>
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
      </Modal>
    </AdminLayout>
  );
}
