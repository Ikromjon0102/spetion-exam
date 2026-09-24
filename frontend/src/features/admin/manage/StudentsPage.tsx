import { useEffect, useState } from "react";
import {
  bulkImportStudents,
  createAdminStudent,
  deleteAdminStudent,
  listAdminClasses,
  listAdminStudents,
  resetClassPasswords,
  updateAdminStudent,
  type BulkImportedStudent,
  type ClassOut,
  type StudentRow,
} from "../../../api/adminApi";
import { AdminLayout, Badge, Button, Card, ConfirmButton, ListRow } from "../../../components/ui";
import { useLanguage } from "../../../i18n/LanguageContext";
import { errorDetail } from "../../../utils/errorDetail";

export default function StudentsPage() {
  const [classes, setClasses] = useState<ClassOut[]>([]);
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [filterClassId, setFilterClassId] = useState<number | "">("");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [studentCode, setStudentCode] = useState("");
  const [newClassId, setNewClassId] = useState<number | "">("");

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { t } = useLanguage();

  const [bulkClassId, setBulkClassId] = useState<number | "">("");
  const [bulkNames, setBulkNames] = useState("");
  const [bulkSubmitting, setBulkSubmitting] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [bulkResult, setBulkResult] = useState<{ created: BulkImportedStudent[]; errors: string[] } | null>(null);

  const [resetClassId, setResetClassId] = useState<number | "">("");
  const [resetPassword, setResetPassword] = useState("");
  const [resetSubmitting, setResetSubmitting] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetSuccess, setResetSuccess] = useState<string | null>(null);
  const [resetConfirming, setResetConfirming] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [rowError, setRowError] = useState<Record<number, string>>({});

  async function reloadStudents(classId: number | "") {
    try {
      setStudents(await listAdminStudents(classId === "" ? undefined : classId));
    } catch {
      setError(t("adminStudents.loadError"));
    }
  }

  useEffect(() => {
    listAdminClasses().then(setClasses).catch(() => undefined);
    reloadStudents("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleFilterChange(value: string) {
    const classId = value === "" ? "" : Number(value);
    setFilterClassId(classId);
    await reloadStudents(classId);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (newClassId === "") return;
    setSubmitting(true);
    try {
      await createAdminStudent({
        username,
        password,
        full_name: fullName,
        class_id: Number(newClassId),
        student_code: studentCode,
      });
      setUsername("");
      setPassword("");
      setFullName("");
      setStudentCode("");
      setNewClassId("");
      await reloadStudents(filterClassId);
    } catch (err) {
      setError(errorDetail(err, t("adminStudents.addError")));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleBulkSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBulkError(null);
    setBulkResult(null);
    if (bulkClassId === "") return;
    const names = bulkNames
      .split("\n")
      .map((n) => n.trim())
      .filter((n) => n.length > 0);
    if (names.length === 0) return;
    setBulkSubmitting(true);
    try {
      const result = await bulkImportStudents(Number(bulkClassId), names);
      setBulkResult(result);
      setBulkNames("");
      await reloadStudents(filterClassId);
    } catch (err) {
      setBulkError(errorDetail(err, t("adminStudents.bulkError")));
    } finally {
      setBulkSubmitting(false);
    }
  }

  function handleResetFormChange() {
    // any edit after a confirm prompt was shown invalidates it — re-confirm
    // against the (possibly different) class/password before applying
    setResetConfirming(false);
    setResetSuccess(null);
  }

  async function handleResetSubmit(e: React.FormEvent) {
    e.preventDefault();
    setResetError(null);
    if (resetClassId === "" || !resetPassword.trim()) return;

    if (!resetConfirming) {
      setResetConfirming(true);
      return;
    }

    setResetSubmitting(true);
    try {
      const result = await resetClassPasswords(Number(resetClassId), resetPassword);
      setResetSuccess(t("adminStudents.resetPwSuccess", { count: result.updated_count }));
      setResetPassword("");
      setResetConfirming(false);
    } catch (err) {
      setResetError(errorDetail(err, t("adminStudents.resetPwError")));
    } finally {
      setResetSubmitting(false);
    }
  }

  async function handleClassChange(student: StudentRow, classId: number) {
    try {
      const updated = await updateAdminStudent(student.id, { class_id: classId });
      setStudents((prev) => prev.map((s) => (s.id === student.id ? updated : s)));
    } catch (err) {
      setError(errorDetail(err, t("adminStudents.addError")));
    }
  }

  async function handleToggleActive(student: StudentRow) {
    try {
      const updated = await updateAdminStudent(student.id, { is_active: !student.is_active });
      setStudents((prev) => prev.map((s) => (s.id === student.id ? updated : s)));
    } catch (err) {
      setError(errorDetail(err, t("adminStudents.addError")));
    }
  }

  async function handleSaveName(studentId: number) {
    setRowError((prev) => ({ ...prev, [studentId]: "" }));
    try {
      const updated = await updateAdminStudent(studentId, { full_name: editName });
      setStudents((prev) => prev.map((s) => (s.id === studentId ? updated : s)));
      setEditingId(null);
    } catch (err) {
      setRowError((prev) => ({ ...prev, [studentId]: errorDetail(err, t("adminStudents.addError")) }));
    }
  }

  async function handleDelete(studentId: number) {
    setRowError((prev) => ({ ...prev, [studentId]: "" }));
    try {
      await deleteAdminStudent(studentId);
      setStudents((prev) => prev.filter((s) => s.id !== studentId));
    } catch (err) {
      setRowError((prev) => ({ ...prev, [studentId]: errorDetail(err, t("adminStudents.deleteError")) }));
    }
  }

  return (
    <AdminLayout>
      <div className="page">
        <h1 className="h2" style={{ marginBottom: "var(--space-6)" }}>
          {t("adminStudents.title")}
        </h1>

        <Card style={{ marginBottom: "var(--space-8)" }}>
          <h2 className="h4" style={{ marginBottom: "var(--space-4)" }}>
            {t("adminStudents.addTitle")}
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
              <select
                className="sp-select"
                value={newClassId}
                onChange={(e) => setNewClassId(Number(e.target.value))}
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
            {error && (
              <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                {error}
              </p>
            )}
            <Button type="submit" disabled={submitting}>
              {t("adminStudents.add")}
            </Button>
          </form>
        </Card>

        <Card style={{ marginBottom: "var(--space-8)" }}>
          <h2 className="h4" style={{ marginBottom: "var(--space-2)" }}>
            {t("adminStudents.bulkTitle")}
          </h2>
          <p className="body-sm" style={{ color: "var(--text-secondary)", marginBottom: "var(--space-4)" }}>
            {t("adminStudents.bulkHint")}
          </p>
          <form onSubmit={handleBulkSubmit} className="stack">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 220px", gap: "var(--space-3)" }}>
              <textarea
                className="sp-input"
                rows={6}
                placeholder={t("adminStudents.bulkPlaceholder")}
                value={bulkNames}
                onChange={(e) => setBulkNames(e.target.value)}
                style={{ resize: "vertical", fontFamily: "inherit" }}
              />
              <div className="stack" style={{ gap: "var(--space-3)" }}>
                <select
                  className="sp-select"
                  value={bulkClassId}
                  onChange={(e) => setBulkClassId(e.target.value === "" ? "" : Number(e.target.value))}
                  required
                >
                  <option value="">{t("adminStudents.bulkClass")}</option>
                  {classes.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.display_name}
                    </option>
                  ))}
                </select>
                <Button type="submit" disabled={bulkSubmitting || bulkClassId === "" || !bulkNames.trim()}>
                  {t("adminStudents.bulkSubmit")}
                </Button>
              </div>
            </div>
            {bulkError && (
              <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                {bulkError}
              </p>
            )}
          </form>

          {bulkResult && (
            <div style={{ marginTop: "var(--space-4)" }}>
              {bulkResult.created.length > 0 && (
                <>
                  <h3 className="h5" style={{ marginBottom: "var(--space-1)" }}>
                    {t("adminStudents.bulkResultTitle")} ({bulkResult.created.length})
                  </h3>
                  <p className="body-sm" style={{ color: "var(--text-secondary)", marginBottom: "var(--space-3)" }}>
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
                </>
              )}
              {bulkResult.errors.length > 0 && (
                <div style={{ marginTop: "var(--space-3)" }}>
                  <h3 className="h5" style={{ color: "var(--danger)", marginBottom: "var(--space-1)" }}>
                    {t("adminStudents.bulkErrorsTitle")}
                  </h3>
                  <ul className="body-sm">
                    {bulkResult.errors.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </Card>

        <Card style={{ marginBottom: "var(--space-8)" }}>
          <h2 className="h4" style={{ marginBottom: "var(--space-2)" }}>
            {t("adminStudents.resetPwTitle")}
          </h2>
          <p className="body-sm" style={{ color: "var(--text-secondary)", marginBottom: "var(--space-4)" }}>
            {t("adminStudents.resetPwHint")}
          </p>
          <form onSubmit={handleResetSubmit} className="stack">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: "var(--space-3)" }}>
              <select
                className="sp-select"
                value={resetClassId}
                onChange={(e) => {
                  setResetClassId(e.target.value === "" ? "" : Number(e.target.value));
                  handleResetFormChange();
                }}
                required
              >
                <option value="">{t("adminStudents.resetPwClass")}</option>
                {classes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.display_name}
                  </option>
                ))}
              </select>
              <input
                className="sp-input"
                placeholder={t("adminStudents.resetPwNewPassword")}
                value={resetPassword}
                onChange={(e) => {
                  setResetPassword(e.target.value);
                  handleResetFormChange();
                }}
                required
              />
              <Button
                type="submit"
                variant={resetConfirming ? "danger" : "primary"}
                disabled={resetSubmitting || resetClassId === "" || !resetPassword.trim()}
              >
                {resetConfirming ? t("adminStudents.resetPwConfirmButton") : t("adminStudents.resetPwSubmit")}
              </Button>
            </div>
            {resetConfirming && (
              <p className="body-sm" style={{ color: "var(--danger)" }}>
                {t("adminStudents.resetPwConfirm", {
                  className: classes.find((c) => c.id === resetClassId)?.display_name ?? "",
                })}
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

        <div className="sp-field" style={{ maxWidth: 260, marginBottom: "var(--space-4)" }}>
          <select className="sp-select" value={filterClassId} onChange={(e) => handleFilterChange(e.target.value)}>
            <option value="">{t("adminStudents.filterAll")}</option>
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.display_name}
              </option>
            ))}
          </select>
        </div>

        <div className="row-stack">
          {students.map((s) =>
            editingId === s.id ? (
              <Card key={s.id}>
                <div className="stack">
                  <input className="sp-input" value={editName} onChange={(e) => setEditName(e.target.value)} required />
                  {rowError[s.id] && (
                    <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                      {rowError[s.id]}
                    </p>
                  )}
                  <div style={{ display: "flex", gap: "var(--space-2)" }}>
                    <Button size="sm" onClick={() => handleSaveName(s.id)}>
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
                  state={s.is_active ? "resting" : "free"}
                  title={s.full_name}
                  subtitle={`${s.username} · ${s.student_code}`}
                  trailing={
                    <>
                      <select
                        className="sp-select"
                        style={{ width: 140 }}
                        value={s.class_id}
                        onChange={(e) => handleClassChange(s, Number(e.target.value))}
                      >
                        {classes.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.display_name}
                          </option>
                        ))}
                      </select>
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
                          setEditingId(s.id);
                          setEditName(s.full_name);
                        }}
                      >
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
