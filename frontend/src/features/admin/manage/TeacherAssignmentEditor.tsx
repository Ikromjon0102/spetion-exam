import { useEffect, useState } from "react";
import {
  addTeacherAssignment,
  listTeacherAssignments,
  removeTeacherAssignment,
  type ClassOut,
  type SubjectOut,
  type TeacherAssignment,
} from "../../../api/adminApi";
import { Badge, Button } from "../../../components/ui";
import { useLanguage } from "../../../i18n/LanguageContext";
import { errorDetail } from "../../../utils/errorDetail";

interface Props {
  teacherId: number;
  classes: ClassOut[];
  subjects: SubjectOut[];
}

export default function TeacherAssignmentEditor({ teacherId, classes, subjects }: Props) {
  const [assignments, setAssignments] = useState<TeacherAssignment[]>([]);
  const [classId, setClassId] = useState<number | "">("");
  const [subjectId, setSubjectId] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);
  const { t } = useLanguage();

  async function reload() {
    try {
      setAssignments(await listTeacherAssignments(teacherId));
    } catch {
      setError(t("adminTeachers.loadError"));
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [teacherId]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (classId === "" || subjectId === "") return;
    try {
      await addTeacherAssignment(teacherId, Number(classId), Number(subjectId));
      setClassId("");
      setSubjectId("");
      await reload();
    } catch (err) {
      setError(errorDetail(err, t("adminTeachers.assignmentAddError")));
    }
  }

  async function handleRemove(linkId: number) {
    try {
      await removeTeacherAssignment(teacherId, linkId);
      await reload();
    } catch (err) {
      setError(errorDetail(err, t("adminTeachers.assignmentAddError")));
    }
  }

  return (
    <div
      style={{
        padding: "var(--space-4)",
        background: "var(--surface-sunken)",
        borderRadius: "var(--radius-md)",
        marginTop: "var(--space-2)",
      }}
    >
      <p className="label-sm" style={{ marginBottom: "var(--space-3)" }}>
        {t("adminTeachers.assignments")}
      </p>
      {assignments.length === 0 && <p className="body-sm ink-muted">{t("adminTeachers.noAssignments")}</p>}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
        {assignments.map((a) => (
          <span key={a.id} style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-1)" }}>
            <Badge status="info">
              {a.class_name} · {a.subject_name}
            </Badge>
            <button
              type="button"
              onClick={() => handleRemove(a.id)}
              aria-label={t("adminTeachers.removeAssignment")}
              style={{
                border: "none",
                background: "transparent",
                color: "var(--danger)",
                cursor: "pointer",
                fontSize: 14,
                lineHeight: 1,
                padding: 2,
              }}
            >
              ✕
            </button>
          </span>
        ))}
      </div>
      <form onSubmit={handleAdd} style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
        <select className="sp-select" style={{ width: 160 }} value={subjectId} onChange={(e) => setSubjectId(Number(e.target.value))}>
          <option value="">{t("upload.selectSubject")}</option>
          {subjects.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <select className="sp-select" style={{ width: 160 }} value={classId} onChange={(e) => setClassId(Number(e.target.value))}>
          <option value="">{t("upload.selectClass")}</option>
          {classes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.display_name}
            </option>
          ))}
        </select>
        <Button type="submit" size="sm" variant="secondary">
          {t("adminTeachers.addAssignment")}
        </Button>
      </form>
      {error && (
        <p role="alert" className="body-sm" style={{ color: "var(--danger)", marginTop: "var(--space-2)" }}>
          {error}
        </p>
      )}
    </div>
  );
}
