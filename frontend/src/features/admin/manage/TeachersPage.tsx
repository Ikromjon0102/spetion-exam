import { useEffect, useState } from "react";
import {
  createAdminTeacher,
  deleteAdminTeacher,
  listAdminClasses,
  listAdminSubjects,
  listAdminTeachers,
  updateAdminTeacher,
  type ClassOut,
  type SubjectOut,
  type TeacherRow,
} from "../../../api/adminApi";
import { AdminLayout, Badge, Button, Card, ConfirmButton, ListRow } from "../../../components/ui";
import { useLanguage } from "../../../i18n/LanguageContext";
import { errorDetail } from "../../../utils/errorDetail";
import TeacherAssignmentEditor from "./TeacherAssignmentEditor";

export default function TeachersPage() {
  const [teachers, setTeachers] = useState<TeacherRow[]>([]);
  const [classes, setClasses] = useState<ClassOut[]>([]);
  const [subjects, setSubjects] = useState<SubjectOut[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [subjectId, setSubjectId] = useState<number | "">("");

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { t } = useLanguage();

  const [editNameId, setEditNameId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [rowError, setRowError] = useState<Record<number, string>>({});

  async function reloadTeachers() {
    try {
      setTeachers(await listAdminTeachers());
    } catch {
      setError(t("adminTeachers.loadError"));
    }
  }

  useEffect(() => {
    reloadTeachers();
    listAdminClasses().then(setClasses).catch(() => undefined);
    listAdminSubjects().then(setSubjects).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await createAdminTeacher({
        username,
        password,
        full_name: fullName,
        subject_id: subjectId === "" ? undefined : Number(subjectId),
      });
      setUsername("");
      setPassword("");
      setFullName("");
      setSubjectId("");
      await reloadTeachers();
    } catch (err) {
      setError(errorDetail(err, t("adminTeachers.addError")));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleActive(teacher: TeacherRow) {
    try {
      const updated = await updateAdminTeacher(teacher.id, { is_active: !teacher.is_active });
      setTeachers((prev) => prev.map((tr) => (tr.id === teacher.id ? updated : tr)));
    } catch (err) {
      setError(errorDetail(err, t("adminTeachers.addError")));
    }
  }

  async function handleSaveName(teacherId: number) {
    setRowError((prev) => ({ ...prev, [teacherId]: "" }));
    try {
      const updated = await updateAdminTeacher(teacherId, { full_name: editName });
      setTeachers((prev) => prev.map((tr) => (tr.id === teacherId ? updated : tr)));
      setEditNameId(null);
    } catch (err) {
      setRowError((prev) => ({ ...prev, [teacherId]: errorDetail(err, t("adminTeachers.addError")) }));
    }
  }

  async function handleDelete(teacherId: number) {
    setRowError((prev) => ({ ...prev, [teacherId]: "" }));
    try {
      await deleteAdminTeacher(teacherId);
      setTeachers((prev) => prev.filter((tr) => tr.id !== teacherId));
    } catch (err) {
      setRowError((prev) => ({ ...prev, [teacherId]: errorDetail(err, t("adminTeachers.deleteError")) }));
    }
  }

  return (
    <AdminLayout>
      <div className="page">
        <h1 className="h2" style={{ marginBottom: "var(--space-6)" }}>
          {t("adminTeachers.title")}
        </h1>

        <Card style={{ marginBottom: "var(--space-8)" }}>
          <h2 className="h4" style={{ marginBottom: "var(--space-4)" }}>
            {t("adminTeachers.addTitle")}
          </h2>
          <form onSubmit={handleSubmit} className="stack">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
              <input
                className="sp-input"
                placeholder={t("login.username")}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
              <input
                className="sp-input"
                type="password"
                placeholder={t("login.password")}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <input
                className="sp-input"
                placeholder={t("adminTeachers.fullName")}
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
              <select className="sp-select" value={subjectId} onChange={(e) => setSubjectId(Number(e.target.value))}>
                <option value="">{t("adminTeachers.mainSubject")}</option>
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            {error && (
              <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                {error}
              </p>
            )}
            <Button type="submit" disabled={submitting}>
              {t("adminTeachers.add")}
            </Button>
          </form>
        </Card>

        <div className="row-stack">
          {teachers.map((teacher) => (
            <div key={teacher.id}>
              <ListRow
                state={teacher.is_active ? "resting" : "free"}
                title={teacher.full_name}
                subtitle={teacher.username}
                chevron
                onClick={() => setExpandedId(expandedId === teacher.id ? null : teacher.id)}
                trailing={
                  <>
                    <Badge status={teacher.is_active ? "success" : "neutral"}>
                      {teacher.is_active ? t("adminStudents.active") : t("adminStudents.inactive")}
                    </Badge>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleToggleActive(teacher);
                      }}
                    >
                      {teacher.is_active ? t("adminTeachers.deactivate") : t("adminTeachers.activate")}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditNameId(teacher.id);
                        setEditName(teacher.full_name);
                      }}
                    >
                      {t("common.edit")}
                    </Button>
                    <span onClick={(e) => e.stopPropagation()}>
                      <ConfirmButton
                        label={t("common.delete")}
                        confirmLabel={t("common.confirmDelete")}
                        onConfirm={() => handleDelete(teacher.id)}
                      />
                    </span>
                  </>
                }
              />
              {rowError[teacher.id] && (
                <p role="alert" className="body-sm" style={{ color: "var(--danger)", marginTop: "var(--space-1)" }}>
                  {rowError[teacher.id]}
                </p>
              )}
              {editNameId === teacher.id && (
                <Card style={{ marginTop: "var(--space-2)" }}>
                  <div className="stack">
                    <label className="sp-field__label">{t("adminTeachers.editName")}</label>
                    <input className="sp-input" value={editName} onChange={(e) => setEditName(e.target.value)} required />
                    <div style={{ display: "flex", gap: "var(--space-2)" }}>
                      <Button size="sm" onClick={() => handleSaveName(teacher.id)}>
                        {t("common.save")}
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => setEditNameId(null)}>
                        {t("common.cancel")}
                      </Button>
                    </div>
                  </div>
                </Card>
              )}
              {expandedId === teacher.id && (
                <TeacherAssignmentEditor teacherId={teacher.id} classes={classes} subjects={subjects} />
              )}
            </div>
          ))}
        </div>
      </div>
    </AdminLayout>
  );
}
