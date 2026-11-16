import { useEffect, useState } from "react";
import {
  createExamTemplate,
  deleteExamTemplate,
  listAdminSubjects,
  listExamTemplates,
  updateExamTemplate,
  type ExamTemplate,
  type SectionKind,
  type SubjectOut,
} from "../../../api/adminApi";
import { AdminLayout, Button, Card, ConfirmButton, ListRow, Modal } from "../../../components/ui";
import { useLanguage } from "../../../i18n/LanguageContext";
import { errorDetail } from "../../../utils/errorDetail";
import { formatPoints } from "../../../utils/formatPoints";
import "../../student/examtaking.css";

interface DraftRow {
  subject_id: number | "";
  kind: SectionKind;
  question_count: string;
  points_per_question: string;
}

const EMPTY_ROW: DraftRow = { subject_id: "", kind: "asosiy", question_count: "", points_per_question: "" };

// The layout every direction shares: two main subjects, three compulsory.
const STARTER_ROWS: DraftRow[] = [
  { subject_id: "", kind: "asosiy", question_count: "30", points_per_question: "3.1" },
  { subject_id: "", kind: "asosiy", question_count: "30", points_per_question: "2.1" },
  { subject_id: "", kind: "majburiy", question_count: "10", points_per_question: "1.1" },
  { subject_id: "", kind: "majburiy", question_count: "10", points_per_question: "1.1" },
  { subject_id: "", kind: "majburiy", question_count: "10", points_per_question: "1.1" },
];

/** Admin-only: the reusable block layouts ("Tibbiyot": Kimyo 30 x 3.1, ...)
 * a chorak exam is created from. Editing one never changes exams that were
 * already created from it. */
export default function ExamTemplatesPage() {
  const { t } = useLanguage();
  const [templates, setTemplates] = useState<ExamTemplate[] | null>(null);
  const [subjects, setSubjects] = useState<SubjectOut[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [duration, setDuration] = useState("180");
  const [rows, setRows] = useState<DraftRow[]>(STARTER_ROWS);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function reload() {
    try {
      setTemplates(await listExamTemplates());
    } catch {
      setLoadError(t("templates.loadError"));
    }
  }

  useEffect(() => {
    reload();
    listAdminSubjects().then(setSubjects).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function openCreate() {
    setEditingId(null);
    setName("");
    setDuration("180");
    setRows(STARTER_ROWS.map((r) => ({ ...r })));
    setFormError(null);
    setOpen(true);
  }

  function openEdit(template: ExamTemplate) {
    setEditingId(template.id);
    setName(template.name);
    setDuration(String(template.duration_minutes));
    setRows(
      template.sections.map((s) => ({
        subject_id: s.subject_id,
        kind: s.kind,
        question_count: String(s.question_count),
        points_per_question: String(s.points_per_question),
      }))
    );
    setFormError(null);
    setOpen(true);
  }

  function patchRow(index: number, patch: Partial<DraftRow>) {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  const totalQuestions = rows.reduce((n, r) => n + (Number(r.question_count) || 0), 0);
  const totalPoints = rows.reduce(
    (n, r) => n + (Number(r.question_count) || 0) * (Number(r.points_per_question.replace(",", ".")) || 0),
    0
  );

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    const sections = rows.map((r) => ({
      subject_id: Number(r.subject_id),
      kind: r.kind,
      question_count: Number(r.question_count),
      points_per_question: Number(r.points_per_question.replace(",", ".")),
    }));
    if (!name.trim()) return setFormError(t("templates.needName"));
    if (sections.some((s) => !s.subject_id || !(s.question_count > 0) || !(s.points_per_question > 0))) {
      return setFormError(t("templates.rowIncomplete"));
    }
    if (new Set(sections.map((s) => s.subject_id)).size !== sections.length) {
      return setFormError(t("templates.subjectTwice"));
    }
    setSaving(true);
    try {
      const body = { name: name.trim(), duration_minutes: Number(duration) || 180, sections };
      if (editingId === null) await createExamTemplate(body);
      else await updateExamTemplate(editingId, body);
      setOpen(false);
      await reload();
    } catch (err) {
      setFormError(errorDetail(err, t("templates.saveError")));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteExamTemplate(id);
      await reload();
    } catch (err) {
      setLoadError(errorDetail(err, t("templates.saveError")));
    }
  }

  return (
    <AdminLayout>
      <div className="page">
        <div className="sp-page-head">
          <div>
            <h1 className="h2">{t("templates.title")}</h1>
            <p className="body-sm ink-muted">{t("templates.subtitle")}</p>
          </div>
          <Button size="sm" onClick={openCreate}>
            + {t("templates.add")}
          </Button>
        </div>

        {loadError && (
          <p role="alert" style={{ color: "var(--danger)", marginBottom: "var(--space-4)" }}>
            {loadError}
          </p>
        )}
        {templates === null && !loadError && <p className="ink-muted">{t("taking.loading")}</p>}
        {templates !== null && templates.length === 0 && (
          <ListRow state="free" title={t("templates.empty")} subtitle={t("templates.emptyHint")} />
        )}

        <div className="sp-card-grid">
          {(templates ?? []).map((template) => (
            <Card key={template.id} className="stack">
              <div className="sp-page-head" style={{ marginBottom: 0 }}>
                <div>
                  <h2 className="h4">{template.name}</h2>
                  <p className="body-sm ink-muted">
                    {template.total_questions} {t("blocks.questionsShort")} · {formatPoints(template.total_points)}{" "}
                    {t("result.points")} · {template.duration_minutes} {t("examList.minutes")}
                  </p>
                </div>
                <div style={{ display: "flex", gap: "var(--space-2)" }}>
                  <Button variant="secondary" size="sm" onClick={() => openEdit(template)}>
                    {t("common.edit")}
                  </Button>
                  <ConfirmButton
                    label={t("common.delete")}
                    confirmLabel={t("common.confirmDelete")}
                    onConfirm={() => handleDelete(template.id)}
                  />
                </div>
              </div>
              <table className="sp-block-table">
                <thead>
                  <tr>
                    <th>{t("blocks.subject")}</th>
                    <th>{t("blocks.questions")}</th>
                    <th>{t("blocks.pointsEach")}</th>
                    <th>{t("blocks.total")}</th>
                  </tr>
                </thead>
                <tbody>
                  {template.sections.map((s) => (
                    <tr key={s.id}>
                      <td>
                        {s.subject_name}
                        <span className="sp-block-table__kind">{t(`blocks.kind.${s.kind}`)}</span>
                      </td>
                      <td>{s.question_count}</td>
                      <td>{formatPoints(s.points_per_question)}</td>
                      <td>{formatPoints(s.question_count * s.points_per_question)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          ))}
        </div>
      </div>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editingId === null ? t("templates.add") : t("templates.edit")}
      >
        <form onSubmit={handleSave} className="stack">
          <div className="sp-form-row">
            <div className="sp-field" style={{ flex: 2 }}>
              <label className="sp-field__label">{t("templates.name")}</label>
              <input
                className="sp-input"
                value={name}
                placeholder={t("templates.namePlaceholder")}
                onChange={(e) => setName(e.target.value)}
                autoFocus
              />
            </div>
            <div className="sp-field" style={{ flex: 1 }}>
              <label className="sp-field__label">{t("review.duration")}</label>
              <input
                className="sp-input"
                type="number"
                min={1}
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
              />
            </div>
          </div>

          <div className="stack" style={{ gap: "var(--space-2)" }}>
            <div className="sp-template-row sp-template-row--head caption">
              <span>{t("blocks.subject")}</span>
              <span>{t("templates.kind")}</span>
              <span>{t("blocks.questions")}</span>
              <span>{t("blocks.pointsEach")}</span>
              <span />
            </div>
            {rows.map((row, i) => (
              <div key={i} className="sp-template-row">
                <select
                  className="sp-select"
                  value={row.subject_id}
                  aria-label={t("blocks.subject")}
                  onChange={(e) => patchRow(i, { subject_id: e.target.value === "" ? "" : Number(e.target.value) })}
                >
                  <option value="">{t("upload.selectSubject")}</option>
                  {subjects.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
                <select
                  className="sp-select"
                  value={row.kind}
                  aria-label={t("templates.kind")}
                  onChange={(e) => patchRow(i, { kind: e.target.value as SectionKind })}
                >
                  <option value="asosiy">{t("blocks.kind.asosiy")}</option>
                  <option value="majburiy">{t("blocks.kind.majburiy")}</option>
                </select>
                <input
                  className="sp-input"
                  type="number"
                  min={1}
                  value={row.question_count}
                  aria-label={t("blocks.questions")}
                  onChange={(e) => patchRow(i, { question_count: e.target.value })}
                />
                <input
                  className="sp-input"
                  inputMode="decimal"
                  value={row.points_per_question}
                  aria-label={t("blocks.pointsEach")}
                  onChange={(e) => patchRow(i, { points_per_question: e.target.value })}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={rows.length <= 1}
                  aria-label={t("common.delete")}
                  onClick={() => setRows((prev) => prev.filter((_, idx) => idx !== i))}
                >
                  ×
                </Button>
              </div>
            ))}
            <div>
              <Button type="button" variant="ghost" size="sm" onClick={() => setRows((prev) => [...prev, { ...EMPTY_ROW }])}>
                + {t("templates.addBlock")}
              </Button>
            </div>
          </div>

          <p className="body-sm">
            <strong>{t("blocks.total")}:</strong> {totalQuestions} {t("blocks.questionsShort")} ·{" "}
            <strong>{formatPoints(totalPoints)}</strong> {t("result.points")}
          </p>
          {formError && (
            <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
              {formError}
            </p>
          )}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={saving}>
              {t("common.save")}
            </Button>
          </div>
        </form>
      </Modal>
    </AdminLayout>
  );
}
