import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getUploadStatus,
  listAdminClasses,
  listAdminSubjects,
  listMyAssignments,
  uploadExamFile,
  type ClassOut,
  type SubjectOut,
  type TeacherAssignment,
} from "../../api/adminApi";
import { AdminLayout, Button, Card, ListRow } from "../../components/ui";
import { useAuth } from "../../auth/AuthContext";
import { useLanguage } from "../../i18n/LanguageContext";

export default function ExamUploadPage() {
  const { user } = useAuth();
  const isTeacher = user?.role === "teacher";

  // Admin: full, independent class/subject lists (unrestricted).
  const [classes, setClasses] = useState<ClassOut[]>([]);
  const [subjects, setSubjects] = useState<SubjectOut[]>([]);
  // Teacher: only their own (class, subject) pairs from teacher_class_subjects
  // — e.g. a teacher who teaches both Huquq and Tarix to different classes
  // only ever sees their own combinations, never the whole school's.
  const [assignments, setAssignments] = useState<TeacherAssignment[]>([]);

  const [classId, setClassId] = useState<number | "">("");
  const [subjectId, setSubjectId] = useState<number | "">("");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { t } = useLanguage();
  const navigate = useNavigate();

  useEffect(() => {
    if (isTeacher) {
      listMyAssignments().then(setAssignments).catch(() => undefined);
    } else {
      listAdminClasses().then(setClasses).catch(() => undefined);
      listAdminSubjects().then(setSubjects).catch(() => undefined);
    }
  }, [isTeacher]);

  const assignedSubjects = useMemo(() => {
    const seen = new Map<number, string>();
    assignments.forEach((a) => seen.set(a.subject_id, a.subject_name));
    return Array.from(seen, ([id, name]) => ({ id, name }));
  }, [assignments]);

  const assignedClassesForSubject = useMemo(() => {
    const seen = new Map<number, string>();
    assignments.filter((a) => a.subject_id === subjectId).forEach((a) => seen.set(a.class_id, a.class_name));
    return Array.from(seen, ([id, name]) => ({ id, name }));
  }, [assignments, subjectId]);

  function handleSubjectChange(value: string) {
    setSubjectId(value === "" ? "" : Number(value));
    setClassId(""); // the class list depends on the subject for teachers
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!file || classId === "" || subjectId === "") return;

    setSubmitting(true);
    try {
      const upload = await uploadExamFile(file, Number(subjectId), Number(classId), title || undefined);
      setStatus(t("upload.parsing"));
      pollUntilParsed(upload.id);
    } catch {
      setError(t("upload.failed"));
      setSubmitting(false);
    }
  }

  function pollUntilParsed(uploadId: number) {
    const interval = setInterval(async () => {
      try {
        const upload = await getUploadStatus(uploadId);
        if (upload.status === "parsed" && upload.exam_id) {
          clearInterval(interval);
          navigate(`/admin/exams/${upload.exam_id}/review`);
        } else if (upload.status === "parse_failed") {
          clearInterval(interval);
          setSubmitting(false);
          setError(upload.parse_error ?? t("upload.parseFailed"));
        } else {
          setStatus(`${t("upload.statusPrefix")}: ${upload.status}`);
        }
      } catch {
        clearInterval(interval);
        setSubmitting(false);
        setError(t("upload.statusCheckFailed"));
      }
    }, 2000);
  }

  if (isTeacher && assignments.length === 0) {
    return (
      <AdminLayout>
        <div className="page" style={{ maxWidth: 480 }}>
          <h1 className="h2" style={{ marginBottom: "var(--space-6)" }}>
            {t("upload.title")}
          </h1>
          <ListRow state="free" title={t("upload.noAssignments")} />
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="page" style={{ maxWidth: 480 }}>
        <h1 className="h2" style={{ marginBottom: "var(--space-6)" }}>
          {t("upload.title")}
        </h1>
        <Card>
          <form onSubmit={handleSubmit} className="stack">
            {isTeacher ? (
              <>
                <div className="sp-field">
                  <label className="sp-field__label">{t("upload.subject")}</label>
                  <select
                    className="sp-select"
                    value={subjectId}
                    onChange={(e) => handleSubjectChange(e.target.value)}
                    required
                  >
                    <option value="">{t("upload.selectSubject")}</option>
                    {assignedSubjects.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="sp-field">
                  <label className="sp-field__label">{t("upload.class")}</label>
                  <select
                    className="sp-select"
                    value={classId}
                    onChange={(e) => setClassId(Number(e.target.value))}
                    disabled={subjectId === ""}
                    required
                  >
                    <option value="">{t("upload.selectClass")}</option>
                    {assignedClassesForSubject.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            ) : (
              <>
                <div className="sp-field">
                  <label className="sp-field__label">{t("upload.class")}</label>
                  <select
                    className="sp-select"
                    value={classId}
                    onChange={(e) => setClassId(Number(e.target.value))}
                    required
                  >
                    <option value="">{t("upload.selectClass")}</option>
                    {classes.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.display_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="sp-field">
                  <label className="sp-field__label">{t("upload.subject")}</label>
                  <select
                    className="sp-select"
                    value={subjectId}
                    onChange={(e) => setSubjectId(Number(e.target.value))}
                    required
                  >
                    <option value="">{t("upload.selectSubject")}</option>
                    {subjects.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            )}
            <div className="sp-field">
              <label className="sp-field__label">{t("upload.titleLabel")}</label>
              <input
                className="sp-input"
                placeholder={t("upload.titlePlaceholder")}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div className="sp-field">
              <label className="sp-field__label">{t("upload.fileLabel")}</label>
              <input
                className="sp-input"
                type="file"
                accept=".pdf,.docx"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                required
              />
            </div>
            {error && (
              <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                {error}
              </p>
            )}
            {status && <p className="body-sm ink-muted">{status}</p>}
            <Button type="submit" block disabled={submitting}>
              {submitting ? t("upload.submitting") : t("upload.submit")}
            </Button>
          </form>
        </Card>
      </div>
    </AdminLayout>
  );
}
