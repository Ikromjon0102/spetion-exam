import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  bulkImportStudents,
  createAdminStudent,
  deleteAdminStudent,
  deleteClass,
  getClassDetail,
  listAdminStudents,
  listAdminTeachers,
  resetClassPasswords,
  updateAdminStudent,
  updateClass,
  type BulkImportedStudent,
  type ClassDetail,
  type StudentRow,
  type TeacherRow,
} from "../../../api/adminApi";
import { useAuth } from "../../../auth/AuthContext";
import { AdminLayout, Badge, Button, Card, ConfirmButton, ListRow } from "../../../components/ui";
import { useLanguage } from "../../../i18n/LanguageContext";
import { errorDetail } from "../../../utils/errorDetail";

export default function ClassDetailPage() {
  const { classId } = useParams();
  const id = Number(classId);
  const { t } = useLanguage();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const navigate = useNavigate();

  const [detail, setDetail] = useState<ClassDetail | null>(null);
  const [teachers, setTeachers] = useState<TeacherRow[]>([]);
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [savingHomeroom, setSavingHomeroom] = useState(false);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [studentCode, setStudentCode] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const [bulkNames, setBulkNames] = useState("");
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [bulkSubmitting, setBulkSubmitting] = useState(false);
  const [bulkResult, setBulkResult] = useState<{ created: BulkImportedStudent[]; errors: string[] } | null>(null);

  const [resetPassword, setResetPassword] = useState("");
  const [resetConfirming, setResetConfirming] = useState(false);
  const [resetSubmitting, setResetSubmitting] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetSuccess, setResetSuccess] = useState<string | null>(null);

  const [editingClass, setEditingClass] = useState(false);
  const [editGrade, setEditGrade] = useState("");
  const [editLabel, setEditLabel] = useState("");
  const [editDisplayName, setEditDisplayName] = useState("");
  const [classEditError, setClassEditError] = useState<string | null>(null);
  const [deleteClassError, setDeleteClassError] = useState<string | null>(null);

  const [editStudentId, setEditStudentId] = useState<number | null>(null);
  const [editStudentName, setEditStudentName] = useState("");
  const [studentRowError, setStudentRowError] = useState<Record<number, string>>({});

  async function reloadDetail() {
    try {
      setDetail(await getClassDetail(id));
    } catch {
      setLoadError(t("classDetail.loadError"));
    }
  }

  async function reloadStudents() {
    try {
      setStudents(await listAdminStudents(id));
    } catch {
      // shouldn't happen once class detail itself loaded (same view-access
      // rule on the backend), but fall back to student_count-only quietly
    }
  }

  useEffect(() => {
    reloadDetail();
    if (isAdmin) listAdminTeachers().then(setTeachers).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    // Any teacher who can see this class's detail page (homeroom, or just
    // teaches a subject here) can also see the roster — only mutating it
    // is homeroom-only, gated separately by `detail.can_manage_students`
    // in the JSX below.
    if (detail) reloadStudents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail?.id, id]);

  async function handleHomeroomChange(teacherId: string) {
    setSavingHomeroom(true);
    try {
      const updated = await updateClass(id, { homeroom_teacher_id: teacherId === "" ? null : Number(teacherId) });
      setDetail((prev) => (prev ? { ...prev, ...updated } : prev));
    } catch {
      setLoadError(t("classDetail.updateError"));
    } finally {
      setSavingHomeroom(false);
    }
  }

  async function handleAddStudent(e: React.FormEvent) {
    e.preventDefault();
    setAddError(null);
    setAdding(true);
    try {
      await createAdminStudent({ username, password, full_name: fullName, class_id: id, student_code: studentCode });
      setUsername("");
      setPassword("");
      setFullName("");
      setStudentCode("");
      await reloadStudents();
      await reloadDetail();
    } catch (err) {
      setAddError(errorDetail(err, t("adminStudents.addError")));
    } finally {
      setAdding(false);
    }
  }

  async function handleBulkSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBulkError(null);
    const names = bulkNames
      .split("\n")
      .map((n) => n.trim())
      .filter(Boolean);
    if (names.length === 0) return;
    setBulkSubmitting(true);
    try {
      const result = await bulkImportStudents(id, names);
      setBulkResult(result);
      setBulkNames("");
      await reloadStudents();
      await reloadDetail();
    } catch (err) {
      setBulkError(errorDetail(err, t("adminStudents.bulkError")));
    } finally {
      setBulkSubmitting(false);
    }
  }

  async function handleToggleActive(student: StudentRow) {
    try {
      const updated = await updateAdminStudent(student.id, { is_active: !student.is_active });
      setStudents((prev) => prev.map((s) => (s.id === student.id ? updated : s)));
    } catch (err) {
      setAddError(errorDetail(err, t("adminStudents.addError")));
    }
  }

  async function handleSaveStudentName(studentId: number) {
    setStudentRowError((prev) => ({ ...prev, [studentId]: "" }));
    try {
      const updated = await updateAdminStudent(studentId, { full_name: editStudentName });
      setStudents((prev) => prev.map((s) => (s.id === studentId ? updated : s)));
      setEditStudentId(null);
    } catch (err) {
      setStudentRowError((prev) => ({ ...prev, [studentId]: errorDetail(err, t("adminStudents.addError")) }));
    }
  }

  async function handleDeleteStudent(studentId: number) {
    setStudentRowError((prev) => ({ ...prev, [studentId]: "" }));
    try {
      await deleteAdminStudent(studentId);
      setStudents((prev) => prev.filter((s) => s.id !== studentId));
      await reloadDetail();
    } catch (err) {
      setStudentRowError((prev) => ({ ...prev, [studentId]: errorDetail(err, t("adminStudents.deleteError")) }));
    }
  }

  function startEditClass() {
    if (!detail) return;
    setEditGrade(String(detail.grade_level));
    setEditLabel(detail.label);
    setEditDisplayName(detail.display_name);
    setClassEditError(null);
    setEditingClass(true);
  }

  async function handleSaveClass() {
    setClassEditError(null);
    try {
      const updated = await updateClass(id, {
        grade_level: Number(editGrade),
        label: editLabel,
        display_name: editDisplayName,
      });
      setDetail((prev) => (prev ? { ...prev, ...updated } : prev));
      setEditingClass(false);
    } catch (err) {
      setClassEditError(errorDetail(err, t("classDetail.updateError")));
    }
  }

  async function handleDeleteClass() {
    setDeleteClassError(null);
    try {
      await deleteClass(id);
      navigate("/classes");
    } catch (err) {
      setDeleteClassError(errorDetail(err, t("classDetail.deleteError")));
    }
  }

  async function handleResetSubmit(e: React.FormEvent) {
    e.preventDefault();
    setResetError(null);
    if (!resetPassword.trim()) return;
    if (!resetConfirming) {
      setResetConfirming(true);
      return;
    }
    setResetSubmitting(true);
    try {
      const result = await resetClassPasswords(id, resetPassword);
      setResetSuccess(t("adminStudents.resetPwSuccess", { count: result.updated_count }));
      setResetPassword("");
      setResetConfirming(false);
    } catch (err) {
      setResetError(errorDetail(err, t("adminStudents.resetPwError")));
    } finally {
      setResetSubmitting(false);
    }
  }

  if (loadError && !detail) {
    return (
      <AdminLayout>
        <div className="page">
          <p role="alert" style={{ color: "var(--danger)" }}>
            {loadError}
          </p>
        </div>
      </AdminLayout>
    );
  }
  if (!detail) {
    return (
      <AdminLayout>
        <div className="page">
          <p className="ink-muted">{t("taking.loading")}</p>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="page">
        <a href="/classes" className="body-sm" style={{ display: "inline-block", marginBottom: "var(--space-3)" }}>
          &larr; {t("classDetail.backToClasses")}
        </a>

        {editingClass ? (
          <Card style={{ marginBottom: "var(--space-6)" }}>
            <div className="stack">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-3)" }}>
                <input
                  className="sp-input"
                  type="number"
                  placeholder={t("adminClasses.grade")}
                  value={editGrade}
                  onChange={(e) => setEditGrade(e.target.value)}
                  required
                />
                <input
                  className="sp-input"
                  placeholder={t("adminClasses.label")}
                  value={editLabel}
                  onChange={(e) => setEditLabel(e.target.value)}
                  required
                />
                <input
                  className="sp-input"
                  placeholder={t("adminClasses.displayName")}
                  value={editDisplayName}
                  onChange={(e) => setEditDisplayName(e.target.value)}
                  required
                />
              </div>
              {classEditError && (
                <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                  {classEditError}
                </p>
              )}
              <div style={{ display: "flex", gap: "var(--space-2)" }}>
                <Button size="sm" onClick={handleSaveClass}>
                  {t("common.save")}
                </Button>
                <Button size="sm" variant="secondary" onClick={() => setEditingClass(false)}>
                  {t("common.cancel")}
                </Button>
              </div>
            </div>
          </Card>
        ) : (
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: "var(--space-3)",
              marginBottom: "var(--space-6)",
            }}
          >
            <div>
              <h1 className="h2" style={{ marginBottom: "var(--space-1)" }}>
                {detail.display_name}
              </h1>
              <p className="body-sm ink-muted">
                {detail.grade_level}-daraja · {detail.label}
              </p>
            </div>
            {isAdmin && (
              <div style={{ display: "flex", gap: "var(--space-2)", flexShrink: 0 }}>
                <Button variant="ghost" size="sm" onClick={startEditClass}>
                  {t("common.edit")}
                </Button>
                <ConfirmButton
                  label={t("common.delete")}
                  confirmLabel={t("common.confirmDelete")}
                  onConfirm={handleDeleteClass}
                />
              </div>
            )}
          </div>
        )}
        {deleteClassError && (
          <p role="alert" className="body-sm" style={{ color: "var(--danger)", marginBottom: "var(--space-4)" }}>
            {deleteClassError}
          </p>
        )}

        <div className="sp-statcard-grid" style={{ marginBottom: "var(--space-6)" }}>
          <Card>
            <div className="data-eyebrow" style={{ marginBottom: "var(--space-1)" }}>
              {t("classDetail.homeroomTeacher")}
            </div>
            {isAdmin ? (
              <select
                className="sp-select"
                value={detail.homeroom_teacher_id ?? ""}
                disabled={savingHomeroom}
                onChange={(e) => handleHomeroomChange(e.target.value)}
              >
                <option value="">{t("classDetail.noHomeroomOption")}</option>
                {teachers.map((tr) => (
                  <option key={tr.id} value={tr.id}>
                    {tr.full_name}
                  </option>
                ))}
              </select>
            ) : (
              <p className="h4" style={{ margin: 0 }}>
                {detail.homeroom_teacher_name ?? t("classDetail.noHomeroomOption")}
              </p>
            )}
          </Card>
          <StatBox label={t("dashboard.students")} value={detail.student_count} />
          <StatBox label={t("adminNav.subjects")} value={detail.subject_assignments.length} />
        </div>

        {detail.subject_assignments.length > 0 && (
          <>
            <h2 className="h4" style={{ marginBottom: "var(--space-3)" }}>
              {t("classDetail.subjectTeachers")}
            </h2>
            <div className="row-stack" style={{ marginBottom: "var(--space-8)" }}>
              {detail.subject_assignments.map((a) => (
                <ListRow key={a.subject_id} title={a.subject_name} subtitle={a.teacher_name} />
              ))}
            </div>
          </>
        )}

        {!detail.can_manage_students && (
          <>
            <h2 className="h4" style={{ marginBottom: "var(--space-2)" }}>
              {t("adminStudents.title")}
            </h2>
            <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-4)" }}>
              {t("classDetail.viewOnlyHint")}
            </p>
            <div className="row-stack">
              {students.map((s) => (
                <ListRow
                  key={s.id}
                  state={s.is_active ? "resting" : "free"}
                  title={s.full_name}
                  subtitle={`${s.username} · ${s.student_code}`}
                  trailing={
                    <Badge status={s.is_active ? "success" : "neutral"}>
                      {s.is_active ? t("adminStudents.active") : t("adminStudents.inactive")}
                    </Badge>
                  }
                />
              ))}
            </div>
          </>
        )}

        {detail.can_manage_students && (
          <>
            <h2 className="h4" style={{ marginBottom: "var(--space-4)" }}>
              {t("adminStudents.title")}
            </h2>

            <Card style={{ marginBottom: "var(--space-6)" }}>
              <h3 className="h5" style={{ marginBottom: "var(--space-4)" }}>
                {t("adminStudents.addTitle")}
              </h3>
              <form onSubmit={handleAddStudent} className="stack">
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
                    placeholder={t("adminStudents.fullName")}
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    required
                  />
                  <input
                    className="sp-input"
                    placeholder={t("adminStudents.studentCode")}
                    value={studentCode}
                    onChange={(e) => setStudentCode(e.target.value)}
                    required
                  />
                </div>
                {addError && (
                  <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                    {addError}
                  </p>
                )}
                <Button type="submit" disabled={adding}>
                  {t("adminStudents.add")}
                </Button>
              </form>
            </Card>

            <Card style={{ marginBottom: "var(--space-6)" }}>
              <h3 className="h5" style={{ marginBottom: "var(--space-2)" }}>
                {t("adminStudents.bulkTitle")}
              </h3>
              <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-4)" }}>
                {t("adminStudents.bulkHint")}
              </p>
              <form onSubmit={handleBulkSubmit} className="stack">
                <textarea
                  className="sp-input"
                  rows={5}
                  placeholder={t("adminStudents.bulkPlaceholder")}
                  value={bulkNames}
                  onChange={(e) => setBulkNames(e.target.value)}
                  style={{ resize: "vertical", fontFamily: "inherit" }}
                />
                {bulkError && (
                  <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                    {bulkError}
                  </p>
                )}
                <Button type="submit" disabled={bulkSubmitting || !bulkNames.trim()}>
                  {t("adminStudents.bulkSubmit")}
                </Button>
              </form>

              {bulkResult && bulkResult.created.length > 0 && (
                <div style={{ marginTop: "var(--space-4)" }}>
                  <h4 className="h5" style={{ marginBottom: "var(--space-1)" }}>
                    {t("adminStudents.bulkResultTitle")} ({bulkResult.created.length})
                  </h4>
                  <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-3)" }}>
                    {t("adminStudents.bulkResultHint")}
                  </p>
                  <div style={{ overflowX: "auto" }}>
                    <table className="body-sm" style={{ width: "100%", borderCollapse: "collapse" }}>
                      <thead>
                        <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
                          <th style={{ padding: "var(--space-2)" }}>{t("adminStudents.fullName")}</th>
                          <th style={{ padding: "var(--space-2)" }}>{t("login.username")}</th>
                          <th style={{ padding: "var(--space-2)" }}>{t("login.password")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {bulkResult.created.map((row) => (
                          <tr key={row.username} style={{ borderBottom: "1px solid var(--border)" }}>
                            <td style={{ padding: "var(--space-2)" }}>{row.full_name}</td>
                            <td style={{ padding: "var(--space-2)", fontFamily: "var(--font-mono)" }}>{row.username}</td>
                            <td style={{ padding: "var(--space-2)", fontFamily: "var(--font-mono)" }}>{row.password}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </Card>

            <Card style={{ marginBottom: "var(--space-8)" }}>
              <h3 className="h5" style={{ marginBottom: "var(--space-2)" }}>
                {t("adminStudents.resetPwTitle")}
              </h3>
              <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-4)" }}>
                {t("adminStudents.resetPwHint")}
              </p>
              <form onSubmit={handleResetSubmit} className="stack">
                <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "var(--space-3)" }}>
                  <input
                    className="sp-input"
                    placeholder={t("adminStudents.resetPwNewPassword")}
                    value={resetPassword}
                    onChange={(e) => {
                      setResetPassword(e.target.value);
                      setResetConfirming(false);
                      setResetSuccess(null);
                    }}
                    required
                  />
                  <Button type="submit" variant={resetConfirming ? "danger" : "primary"} disabled={resetSubmitting || !resetPassword.trim()}>
                    {resetConfirming ? t("adminStudents.resetPwConfirmButton") : t("adminStudents.resetPwSubmit")}
                  </Button>
                </div>
                {resetConfirming && (
                  <p className="body-sm" style={{ color: "var(--danger)" }}>
                    {t("adminStudents.resetPwConfirm", { className: detail.display_name })}
                  </p>
                )}
                {resetError && (
                  <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                    {resetError}
                  </p>
                )}
                {resetSuccess && (
                  <p className="body-sm" style={{ color: "var(--success)" }}>
                    {resetSuccess}
                  </p>
                )}
              </form>
            </Card>

            <div className="row-stack">
              {students.map((s) =>
                editStudentId === s.id ? (
                  <Card key={s.id}>
                    <div className="stack">
                      <input
                        className="sp-input"
                        value={editStudentName}
                        onChange={(e) => setEditStudentName(e.target.value)}
                        required
                      />
                      {studentRowError[s.id] && (
                        <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                          {studentRowError[s.id]}
                        </p>
                      )}
                      <div style={{ display: "flex", gap: "var(--space-2)" }}>
                        <Button size="sm" onClick={() => handleSaveStudentName(s.id)}>
                          {t("common.save")}
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => setEditStudentId(null)}>
                          {t("common.cancel")}
                        </Button>
                      </div>
                    </div>
                  </Card>
                ) : (
                  <div key={s.id}>
                    <ListRow
                      state={s.is_active ? "resting" : "free"}
                      title={s.full_name}
                      subtitle={`${s.username} · ${s.student_code}`}
                      trailing={
                        <>
                          <Badge status={s.is_active ? "success" : "neutral"}>
                            {s.is_active ? t("adminStudents.active") : t("adminStudents.inactive")}
                          </Badge>
                          <Button variant="ghost" size="sm" onClick={() => handleToggleActive(s)}>
                            {s.is_active ? t("adminStudents.deactivate") : t("adminStudents.activate")}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setEditStudentId(s.id);
                              setEditStudentName(s.full_name);
                            }}
                          >
                            {t("common.edit")}
                          </Button>
                          <ConfirmButton
                            label={t("common.delete")}
                            confirmLabel={t("common.confirmDelete")}
                            onConfirm={() => handleDeleteStudent(s.id)}
                          />
                        </>
                      }
                    />
                    {studentRowError[s.id] && (
                      <p role="alert" className="body-sm" style={{ color: "var(--danger)", marginTop: "var(--space-1)" }}>
                        {studentRowError[s.id]}
                      </p>
                    )}
                  </div>
                )
              )}
            </div>
          </>
        )}
      </div>
    </AdminLayout>
  );
}

function StatBox({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <div className="data-eyebrow" style={{ marginBottom: "var(--space-1)" }}>
        {label}
      </div>
      <div className="h2" style={{ margin: 0, fontFamily: "var(--font-mono)" }}>
        {value}
      </div>
    </Card>
  );
}
