import { useEffect, useState } from "react";
import { createSubject, deleteSubject, listAdminSubjects, updateSubject, type SubjectOut } from "../../../api/adminApi";
import { AdminLayout, Button, Card, ConfirmButton, ListRow } from "../../../components/ui";
import { useLanguage } from "../../../i18n/LanguageContext";
import { errorDetail } from "../../../utils/errorDetail";

export default function SubjectsPage() {
  const [subjects, setSubjects] = useState<SubjectOut[]>([]);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { t } = useLanguage();

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editCode, setEditCode] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [rowError, setRowError] = useState<Record<number, string>>({});

  async function reload() {
    try {
      setSubjects(await listAdminSubjects());
    } catch {
      setError(t("adminSubjects.loadError"));
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await createSubject({ name, code: code || undefined });
      setName("");
      setCode("");
      await reload();
    } catch (err) {
      setError(errorDetail(err, t("adminSubjects.addError")));
    } finally {
      setSubmitting(false);
    }
  }

  function startEdit(subject: SubjectOut) {
    setEditingId(subject.id);
    setEditName(subject.name);
    setEditCode(subject.code ?? "");
    setEditError(null);
  }

  async function handleSaveEdit(subjectId: number) {
    setEditError(null);
    try {
      await updateSubject(subjectId, { name: editName, code: editCode || null });
      setEditingId(null);
      await reload();
    } catch (err) {
      setEditError(errorDetail(err, t("adminSubjects.addError")));
    }
  }

  async function handleDelete(subjectId: number) {
    setRowError((prev) => ({ ...prev, [subjectId]: "" }));
    try {
      await deleteSubject(subjectId);
      await reload();
    } catch (err) {
      setRowError((prev) => ({ ...prev, [subjectId]: errorDetail(err, t("adminSubjects.deleteError")) }));
    }
  }

  return (
    <AdminLayout>
      <div className="page">
        <h1 className="h2" style={{ marginBottom: "var(--space-6)" }}>
          {t("adminSubjects.title")}
        </h1>

        <Card style={{ marginBottom: "var(--space-8)" }}>
          <h2 className="h4" style={{ marginBottom: "var(--space-4)" }}>
            {t("adminSubjects.addTitle")}
          </h2>
          <form onSubmit={handleSubmit} className="stack">
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "var(--space-3)" }}>
              <input
                className="sp-input"
                placeholder={t("adminSubjects.name")}
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
              <input
                className="sp-input"
                placeholder={t("adminSubjects.code")}
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </div>
            {error && (
              <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                {error}
              </p>
            )}
            <Button type="submit" disabled={submitting}>
              {t("adminSubjects.add")}
            </Button>
          </form>
        </Card>

        <div className="row-stack">
          {subjects.map((s) =>
            editingId === s.id ? (
              <Card key={s.id}>
                <div className="stack">
                  <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "var(--space-3)" }}>
                    <input className="sp-input" value={editName} onChange={(e) => setEditName(e.target.value)} required />
                    <input className="sp-input" value={editCode} onChange={(e) => setEditCode(e.target.value)} />
                  </div>
                  {editError && (
                    <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                      {editError}
                    </p>
                  )}
                  <div style={{ display: "flex", gap: "var(--space-2)" }}>
                    <Button size="sm" onClick={() => handleSaveEdit(s.id)}>
                      {t("common.save")}
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => setEditingId(null)}>
                      {t("common.cancel")}
                    </Button>
                  </div>
                </div>
              </Card>
            ) : (
              <div key={s.id}>
                <ListRow
                  title={s.name}
                  subtitle={s.code ?? undefined}
                  trailing={
                    <>
                      <Button variant="ghost" size="sm" onClick={() => startEdit(s)}>
                        {t("common.edit")}
                      </Button>
                      <ConfirmButton
                        label={t("common.delete")}
                        confirmLabel={t("common.confirmDelete")}
                        onConfirm={() => handleDelete(s.id)}
                      />
                    </>
                  }
                />
                {rowError[s.id] && (
                  <p role="alert" className="body-sm" style={{ color: "var(--danger)", marginTop: "var(--space-1)" }}>
                    {rowError[s.id]}
                  </p>
                )}
              </div>
            )
          )}
        </div>
      </div>
    </AdminLayout>
  );
}
