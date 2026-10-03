import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  addQuestion,
  clearOptionImage,
  clearQuestionPromptImage,
  deleteExam,
  deleteQuestion,
  duplicateExam,
  getExamDetail,
  listAdminClasses,
  listMyAssignments,
  publishExam,
  questionImageUrl,
  setOptionImage,
  setQuestionPromptImage,
  updateExam,
  updateQuestion,
  updateQuestionOption,
  type ClassOut,
  type ExamDetail,
  type ExamSummary,
} from "../../api/adminApi";
import { useAuth } from "../../auth/AuthContext";
import {
  AdminLayout,
  AuthedImage,
  Badge,
  Button,
  Card,
  CardFoot,
  CardHead,
  ConfirmButton,
  Modal,
  Toast,
  type BadgeStatus,
} from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";
import { errorDetail } from "../../utils/errorDetail";
// RichText / RichTextEditor are imported by path, not through the ui barrel (see
// components/ui/index.ts) so TipTap stays in this lazy page's chunk.
import RichText from "../../components/ui/RichText";
import RichTextEditor from "../../components/ui/RichTextEditor";

// The header badge shows the exam's phase (from its time window), not
// Exam.status — which stays "scheduled" long after the exam is over.
const PHASE_KEY: Record<string, { status: BadgeStatus; key: string }> = {
  draft: { status: "neutral", key: "phase.draft" },
  upcoming: { status: "info", key: "phase.upcoming" },
  live: { status: "warning", key: "phase.live" },
  finished: { status: "success", key: "phase.finished" },
};

/** Local preview of a not-yet-uploaded pasted image (the "Yangi savol
 * qo'shish" form's fields aren't real questions/options yet, so there's
 * nothing to fetch from the server — just show the File directly). */
function PendingImagePreview({ file, maxHeight }: { file: File; maxHeight?: number }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);
  if (!url) return null;
  return (
    <img
      src={url}
      alt=""
      style={{ maxWidth: "100%", maxHeight, borderRadius: "var(--radius-md)", border: "1px solid var(--border)" }}
    />
  );
}

function toLocalInputValue(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function ExamReviewEditor() {
  const { examId } = useParams();
  const id = Number(examId);
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [exam, setExam] = useState<ExamDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  // Bumped on every notify() so two identical "Saqlandi" toasts in a row
  // each get a fresh auto-dismiss timer instead of sharing the first one's.
  const [messageKey, setMessageKey] = useState(0);
  // The one existing question currently open in the rich editor, with its
  // unsaved draft. Saved explicitly (Saqlash) — a rich editor can't sensibly
  // autosave on blur the way a plain field does.
  const [editing, setEditing] = useState<{
    questionId: number;
    prompt: string;
    options: Record<number, string>;
  } | null>(null);
  // Bumped after a question is added so the new-question editors remount empty.
  const [formKey, setFormKey] = useState(0);
  const [newQuestion, setNewQuestion] = useState({
    question_type: "mcq" as "mcq" | "short_answer",
    prompt_text: "",
    options: ["", "", "", ""],
    correctIndex: 0,
    promptImageFile: null as File | null,
    optionImageFiles: [null, null, null, null] as (File | null)[],
    reference_answer: "",
  });

  // "Nusxalash" — a teacher teaching the identical lesson to several
  // parallel classes (e.g. 7B and 7R) can copy this exam's full content
  // into one or more sibling classes instead of re-authoring/re-uploading
  // it per class. See POST /admin/exams/{id}/duplicate.
  const [duplicateOpen, setDuplicateOpen] = useState(false);
  const [duplicateTargets, setDuplicateTargets] = useState<{ id: number; name: string }[]>([]);
  const [selectedClassIds, setSelectedClassIds] = useState<Set<number>>(new Set());
  const [duplicating, setDuplicating] = useState(false);
  const [duplicateError, setDuplicateError] = useState<string | null>(null);
  const [duplicateResult, setDuplicateResult] = useState<ExamSummary[] | null>(null);

  async function reload() {
    try {
      setExam(await getExamDetail(id));
    } catch {
      setError(t("review.loadError"));
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (error && !exam) {
    return (
      <AdminLayout>
        <div className="page">
          <p role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </p>
        </div>
      </AdminLayout>
    );
  }
  if (!exam) {
    return (
      <AdminLayout>
        <div className="page">
          <p className="ink-muted">{t("taking.loading")}</p>
        </div>
      </AdminLayout>
    );
  }

  // Editable right up until a student actually starts the exam — a
  // published (scheduled/active) exam is still fair game as long as
  // exam.can_edit says nobody's begun it yet (see exam_service.ensure_no_attempts).
  const locked = !exam.can_edit;
  const canPublish = exam.status === "draft" || exam.status === "review";

  function notify(text: string) {
    setError(null);
    setMessage(text);
    setMessageKey((k) => k + 1);
  }

  async function saveSchedule(
    patch: Partial<{ duration_minutes: number; start_at: string; end_at: string; expected_question_count: number | null }>
  ) {
    try {
      await updateExam(id, patch);
      await reload();
      notify(t("review.saved"));
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  async function saveQuestion(
    questionId: number,
    patch: Partial<{ prompt_text: string; points: number; needs_review: boolean; reference_answer: string }>
  ) {
    try {
      await updateQuestion(id, questionId, patch);
      await reload();
      notify(t("review.saved"));
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  async function setCorrectOption(questionId: number, optionId: number) {
    const question = exam?.questions.find((q) => q.id === questionId);
    const previous = question?.options.find((o) => o.is_correct && o.id !== optionId);
    try {
      if (previous) await updateQuestionOption(id, questionId, previous.id, { is_correct: false });
      await updateQuestionOption(id, questionId, optionId, { is_correct: true });
      await reload();
      notify(t("review.saved"));
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  async function uploadPromptImage(questionId: number, file: File) {
    try {
      await setQuestionPromptImage(id, questionId, file);
      await reload();
      notify(t("review.saved"));
    } catch (err) {
      setError(errorDetail(err, t("review.genericError")));
    }
  }

  async function handleClearPromptImage(questionId: number) {
    try {
      await clearQuestionPromptImage(id, questionId);
      await reload();
      notify(t("review.saved"));
    } catch (err) {
      setError(errorDetail(err, t("review.genericError")));
    }
  }

  async function uploadOptionImage(questionId: number, optionId: number, file: File) {
    try {
      await setOptionImage(id, questionId, optionId, file);
      await reload();
      notify(t("review.saved"));
    } catch (err) {
      setError(errorDetail(err, t("review.genericError")));
    }
  }

  async function handleClearOptionImage(questionId: number, optionId: number) {
    try {
      await clearOptionImage(id, questionId, optionId);
      await reload();
      notify(t("review.saved"));
    } catch (err) {
      setError(errorDetail(err, t("review.genericError")));
    }
  }

  function startEdit(q: ExamDetail["questions"][number]) {
    setEditing({
      questionId: q.id,
      prompt: q.prompt_text,
      options: Object.fromEntries(q.options.map((o) => [o.id, o.option_text])),
    });
  }

  async function saveEdit() {
    if (!editing || !exam) return;
    const q = exam.questions.find((item) => item.id === editing.questionId);
    if (!q) return;
    if (!editing.prompt.trim() && !q.prompt_image_key) {
      setError(t("review.needsTextOrImage"));
      return;
    }
    for (let i = 0; i < q.options.length; i++) {
      const opt = q.options[i];
      const text = editing.options[opt.id] ?? opt.option_text;
      if (!text.trim() && !opt.option_image_key) {
        setError(t("review.optionEmpty", { letter: String.fromCharCode(65 + i) }));
        return;
      }
    }
    try {
      if (editing.prompt !== q.prompt_text) await updateQuestion(id, q.id, { prompt_text: editing.prompt });
      for (const opt of q.options) {
        const next = editing.options[opt.id];
        if (next !== undefined && next !== opt.option_text) await updateQuestionOption(id, q.id, opt.id, { option_text: next });
      }
      setEditing(null);
      await reload();
      notify(t("review.saved"));
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  async function removeQuestion(questionId: number) {
    try {
      await deleteQuestion(id, questionId);
      await reload();
      notify(t("review.questionDeleted"));
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  async function handleAddQuestion(e: React.FormEvent) {
    e.preventDefault();
    if (!newQuestion.prompt_text.trim() && !newQuestion.promptImageFile) {
      setError(t("review.needsTextOrImage"));
      return;
    }
    if (newQuestion.question_type === "short_answer") {
      if (!newQuestion.reference_answer.trim()) {
        setError(t("review.needsReferenceAnswer"));
        return;
      }
    } else {
      for (let i = 0; i < newQuestion.options.length; i++) {
        if (!newQuestion.options[i].trim() && !newQuestion.optionImageFiles[i]) {
          setError(t("review.optionEmpty", { letter: String.fromCharCode(65 + i) }));
          return;
        }
      }
    }
    try {
      const created = await addQuestion(id, {
        question_type: newQuestion.question_type,
        prompt_text: newQuestion.prompt_text,
        reference_answer: newQuestion.question_type === "short_answer" ? newQuestion.reference_answer : undefined,
        options:
          newQuestion.question_type === "short_answer"
            ? []
            : newQuestion.options.map((text, i) => ({ option_text: text, is_correct: i === newQuestion.correctIndex })),
      });
      if (newQuestion.promptImageFile) {
        await setQuestionPromptImage(id, created.id, newQuestion.promptImageFile);
      }
      for (let i = 0; i < newQuestion.optionImageFiles.length; i++) {
        const file = newQuestion.optionImageFiles[i];
        if (file) await setOptionImage(id, created.id, created.options[i].id, file);
      }
      setNewQuestion({
        question_type: "mcq",
        prompt_text: "",
        options: ["", "", "", ""],
        correctIndex: 0,
        promptImageFile: null,
        optionImageFiles: [null, null, null, null],
        reference_answer: "",
      });
      setFormKey((k) => k + 1);
      await reload();
      notify(t("review.questionAdded", { count: (exam?.questions.length ?? 0) + 1 }));
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  function setNewPromptImage(file: File) {
    setNewQuestion((prev) => ({ ...prev, promptImageFile: file }));
  }

  function setNewOptionImage(index: number, file: File) {
    setNewQuestion((prev) => {
      const optionImageFiles = [...prev.optionImageFiles];
      optionImageFiles[index] = file;
      return { ...prev, optionImageFiles };
    });
  }

  // Publishing only requires >=2 options now (was a fixed 4) — a
  // True/False question, a 3-option one, a 5-option one, whatever the
  // teacher's source material actually has.
  const MAX_NEW_OPTIONS = 8;

  function addOptionSlot() {
    setNewQuestion((prev) =>
      prev.options.length >= MAX_NEW_OPTIONS
        ? prev
        : { ...prev, options: [...prev.options, ""], optionImageFiles: [...prev.optionImageFiles, null] }
    );
  }

  function removeOptionSlot(index: number) {
    setNewQuestion((prev) => {
      if (prev.options.length <= 2) return prev;
      const options = prev.options.filter((_, i) => i !== index);
      const optionImageFiles = prev.optionImageFiles.filter((_, i) => i !== index);
      let correctIndex = prev.correctIndex;
      if (correctIndex === index) correctIndex = 0;
      else if (correctIndex > index) correctIndex -= 1;
      return { ...prev, options, optionImageFiles, correctIndex };
    });
  }

  async function handlePublish() {
    setMessage(null);
    setError(null);
    try {
      await publishExam(id);
      // Land on the exam list with a confirmation — the publish button is
      // at the very bottom of a long page, so a message left up here was
      // easy to miss entirely and the page looked like it had frozen.
      navigate("/admin/exams", { state: { flash: t("review.published") } });
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  async function openDuplicateModal() {
    if (!exam) return;
    setDuplicateError(null);
    setDuplicateResult(null);
    setSelectedClassIds(new Set());
    try {
      if (isAdmin) {
        const classes: ClassOut[] = await listAdminClasses();
        setDuplicateTargets(
          classes.filter((c) => c.id !== exam.class_id).map((c) => ({ id: c.id, name: c.display_name }))
        );
      } else {
        const assignments = await listMyAssignments();
        const seen = new Map<number, string>();
        assignments
          .filter((a) => a.subject_id === exam.subject_id && a.class_id !== exam.class_id)
          .forEach((a) => seen.set(a.class_id, a.class_name));
        setDuplicateTargets(Array.from(seen, ([classId, name]) => ({ id: classId, name })));
      }
      setDuplicateOpen(true);
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  function toggleDuplicateTarget(classId: number) {
    setSelectedClassIds((prev) => {
      const next = new Set(prev);
      if (next.has(classId)) next.delete(classId);
      else next.add(classId);
      return next;
    });
  }

  async function handleDeleteExam() {
    try {
      await deleteExam(id);
      navigate("/admin/exams");
    } catch (e) {
      setError(errorDetail(e, t("review.deleteError")));
    }
  }

  async function handleDuplicateSubmit() {
    if (selectedClassIds.size === 0) return;
    setDuplicating(true);
    setDuplicateError(null);
    try {
      const created = await duplicateExam(id, Array.from(selectedClassIds));
      setDuplicateResult(created);
      setSelectedClassIds(new Set());
    } catch (e) {
      setDuplicateError(errorDetail(e, t("review.genericError")));
    } finally {
      setDuplicating(false);
    }
  }

  const statusBadge = PHASE_KEY[exam.phase];

  return (
    <AdminLayout>
      <div className="page">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--space-3)",
            marginBottom: "var(--space-1)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            <h1 className="h2">{exam.title}</h1>
            <Badge status={statusBadge?.status ?? "neutral"}>{statusBadge ? t(statusBadge.key) : exam.status}</Badge>
            {exam.archived_at && <Badge status="neutral">{t("examArchive.tabArchive")}</Badge>}
          </div>
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            <Button variant="secondary" size="sm" onClick={openDuplicateModal}>
              {t("review.duplicate")}
            </Button>
            {(!locked || isAdmin) && (
              <ConfirmButton
                label={t("common.delete")}
                confirmLabel={t("common.confirmDelete")}
                onConfirm={handleDeleteExam}
              />
            )}
          </div>
        </div>
        <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-6)" }}>
          {exam.subject_name} · {exam.class_name}
        </p>

        {error && <Toast kind="error" text={error} onClose={() => setError(null)} />}
        {message && (
          <Toast
            key={messageKey}
            kind="success"
            text={message}
            autoDismissMs={3000}
            onClose={() => setMessage(null)}
          />
        )}
        {locked && (
          <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-4)" }}>
            {t("review.lockedHint")}
          </p>
        )}

        <Card className="stack" style={{ marginBottom: "var(--space-8)" }}>
          <h2 className="h4">{t("review.schedule")}</h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-4)" }}>
            <div className="sp-field">
              <label className="sp-field__label">{t("review.duration")}</label>
              <input
                className="sp-input"
                type="number"
                defaultValue={exam.duration_minutes}
                disabled={locked}
                onBlur={(e) => saveSchedule({ duration_minutes: Number(e.target.value) })}
              />
            </div>
            <div className="sp-field">
              <label className="sp-field__label">{t("review.startAt")}</label>
              <input
                className="sp-input"
                type="datetime-local"
                defaultValue={toLocalInputValue(exam.start_at)}
                disabled={locked}
                onBlur={(e) => e.target.value && saveSchedule({ start_at: new Date(e.target.value).toISOString() })}
              />
            </div>
            <div className="sp-field">
              <label className="sp-field__label">{t("review.endAt")}</label>
              <input
                className="sp-input"
                type="datetime-local"
                defaultValue={toLocalInputValue(exam.end_at)}
                disabled={locked}
                onBlur={(e) => e.target.value && saveSchedule({ end_at: new Date(e.target.value).toISOString() })}
              />
            </div>
          </div>
        </Card>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-4)" }}>
          <h2 className="h3">{t("review.questions")}</h2>
          <span className="body-sm ink-muted">
            {exam.question_count} {t("review.questionsCount")} · {exam.needs_review_count} {t("review.needsReviewCount")}
          </span>
        </div>
        {!locked && (
          <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-4)" }}>
            {t("review.autosaveHint")}
          </p>
        )}
        <div className="sp-field" style={{ maxWidth: 280, marginBottom: "var(--space-4)" }}>
          <label className="sp-field__label">{t("review.expectedCountLabel")}</label>
          <input
            className="sp-input"
            type="number"
            min={1}
            defaultValue={exam.expected_question_count ?? ""}
            disabled={locked}
            placeholder={t("review.expectedCountPlaceholder")}
            onBlur={(e) => {
              const next = Number(e.target.value) > 0 ? Number(e.target.value) : null;
              if (next !== exam.expected_question_count) saveSchedule({ expected_question_count: next });
            }}
          />
        </div>
        {exam.expected_question_count !== null && exam.question_count !== exam.expected_question_count && (
          <p
            role="status"
            className="body-sm"
            style={{
              marginBottom: "var(--space-4)",
              padding: "var(--space-3) var(--space-4)",
              border: "1.5px solid var(--warning)",
              borderRadius: "var(--radius-md)",
              color: "var(--warning)",
            }}
          >
            {t("review.countMismatch", { expected: exam.expected_question_count, actual: exam.question_count })}
          </p>
        )}

        <div className="stack" style={{ marginBottom: "var(--space-6)" }}>
          {exam.questions.map((q, idx) => (
            <Card key={q.id}>
              <CardHead>
                <span className="data-eyebrow">
                  {t("review.question")} {idx + 1}
                </span>
                {q.needs_review && <Badge status="warning">{t("review.needsReviewBadge")}</Badge>}
                {q.parse_confidence === "low" && (
                  <Badge status="danger">{t("review.lowConfidenceBadge")}</Badge>
                )}
              </CardHead>
              {q.prompt_image_key ? (
                <div style={{ marginBottom: "var(--space-4)" }}>
                  <AuthedImage src={questionImageUrl(q.prompt_image_key)} alt={t("review.question")} maxHeight={280} />
                  {!locked && (
                    <Button
                      variant="ghost"
                      size="sm"
                      style={{ marginTop: "var(--space-2)" }}
                      onClick={() => handleClearPromptImage(q.id)}
                    >
                      {t("review.revertToText")}
                    </Button>
                  )}
                </div>
              ) : editing?.questionId === q.id ? (
                <div style={{ marginBottom: "var(--space-4)" }}>
                  <RichTextEditor
                    value={editing.prompt}
                    placeholder={t("review.pasteHint")}
                    onChange={(v) => setEditing((prev) => (prev ? { ...prev, prompt: v } : prev))}
                    onPasteImage={(file) => uploadPromptImage(q.id, file)}
                    autoFocus
                  />
                </div>
              ) : (
                <div className="body" style={{ marginBottom: "var(--space-4)" }}>
                  <RichText block text={q.prompt_text} />
                </div>
              )}
              {q.question_type === "short_answer" ? (
                <div className="sp-field">
                  <label className="sp-field__label">{t("review.referenceAnswerLabel")}</label>
                  <textarea
                    className="sp-input"
                    defaultValue={q.reference_answer ?? ""}
                    disabled={locked}
                    rows={2}
                    placeholder={t("review.referenceAnswerPlaceholder")}
                    style={{ resize: "vertical" }}
                    onBlur={(e) => saveQuestion(q.id, { reference_answer: e.target.value })}
                  />
                </div>
              ) : (
                <div className="stack" style={{ gap: "var(--space-2)" }}>
                  {q.options.map((opt) => (
                    <div key={opt.id} style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                      <input
                        type="radio"
                        name={`correct-${q.id}`}
                        checked={opt.is_correct}
                        disabled={locked}
                        onChange={() => setCorrectOption(q.id, opt.id)}
                        style={{ accentColor: "var(--brand-600)", width: 18, height: 18, flexShrink: 0 }}
                      />
                      {opt.option_image_key ? (
                        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flex: 1 }}>
                          <AuthedImage src={questionImageUrl(opt.option_image_key)} maxHeight={60} />
                          {!locked && (
                            <Button variant="ghost" size="sm" onClick={() => handleClearOptionImage(q.id, opt.id)}>
                              {t("review.revertToText")}
                            </Button>
                          )}
                        </div>
                      ) : editing?.questionId === q.id ? (
                        <div style={{ flex: 1 }}>
                          <RichTextEditor
                            compact
                            value={editing.options[opt.id] ?? opt.option_text}
                            placeholder={t("review.pasteHint")}
                            onChange={(v) =>
                              setEditing((prev) => (prev ? { ...prev, options: { ...prev.options, [opt.id]: v } } : prev))
                            }
                            onPasteImage={(file) => uploadOptionImage(q.id, opt.id, file)}
                          />
                        </div>
                      ) : (
                        <div className="body" style={{ flex: 1 }}>
                          <RichText text={opt.option_text} />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
              <CardFoot>
                <label className="body-sm" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                  <input
                    type="checkbox"
                    checked={q.needs_review}
                    disabled={locked}
                    onChange={(e) => saveQuestion(q.id, { needs_review: e.target.checked })}
                    style={{ accentColor: "var(--brand-600)" }}
                  />
                  {t("review.needsReviewCheckbox")}
                </label>
                <div style={{ display: "flex", gap: "var(--space-2)" }}>
                  {editing?.questionId === q.id ? (
                    <>
                      <Button size="sm" onClick={saveEdit}>
                        {t("review.saveChanges")}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setEditing(null)}>
                        {t("richEditor.cancel")}
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={locked || editing !== null}
                        onClick={() => startEdit(q)}
                      >
                        {t("review.editQuestion")}
                      </Button>
                      <Button variant="ghost" size="sm" disabled={locked} onClick={() => removeQuestion(q.id)}>
                        {t("review.delete")}
                      </Button>
                    </>
                  )}
                </div>
              </CardFoot>
            </Card>
          ))}
        </div>

        {!locked && (
          <Card style={{ marginBottom: "var(--space-8)" }}>
            <h3 className="h4" style={{ marginBottom: "var(--space-4)" }}>
              {t("review.addQuestion")}
            </h3>
            <form onSubmit={handleAddQuestion} className="stack">
              <div style={{ display: "flex", gap: "var(--space-2)" }}>
                <Button
                  type="button"
                  size="sm"
                  variant={newQuestion.question_type === "mcq" ? "primary" : "secondary"}
                  onClick={() => setNewQuestion((prev) => ({ ...prev, question_type: "mcq" }))}
                >
                  {t("review.typeMcq")}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={newQuestion.question_type === "short_answer" ? "primary" : "secondary"}
                  onClick={() => setNewQuestion((prev) => ({ ...prev, question_type: "short_answer" }))}
                >
                  {t("review.typeShortAnswer")}
                </Button>
              </div>
              {newQuestion.promptImageFile ? (
                <div>
                  <PendingImagePreview file={newQuestion.promptImageFile} maxHeight={280} />
                  <Button
                    variant="ghost"
                    size="sm"
                    style={{ marginTop: "var(--space-2)" }}
                    onClick={() => setNewQuestion((prev) => ({ ...prev, promptImageFile: null }))}
                  >
                    {t("review.revertToText")}
                  </Button>
                </div>
              ) : (
                <RichTextEditor
                  key={`new-prompt-${formKey}`}
                  value=""
                  placeholder={`${t("review.promptPlaceholder")} — ${t("review.pasteHint")}`}
                  onChange={(v) => setNewQuestion((prev) => ({ ...prev, prompt_text: v }))}
                  onPasteImage={setNewPromptImage}
                />
              )}
              {newQuestion.question_type === "short_answer" ? (
                <div className="sp-field">
                  <label className="sp-field__label">{t("review.referenceAnswerLabel")}</label>
                  <textarea
                    className="sp-input"
                    placeholder={t("review.referenceAnswerPlaceholder")}
                    value={newQuestion.reference_answer}
                    onChange={(e) => setNewQuestion({ ...newQuestion, reference_answer: e.target.value })}
                    rows={2}
                    style={{ resize: "vertical" }}
                  />
                </div>
              ) : (
                <>
                  {newQuestion.options.map((text, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                      <input
                        type="radio"
                        name="new-correct"
                        checked={newQuestion.correctIndex === i}
                        onChange={() => setNewQuestion({ ...newQuestion, correctIndex: i })}
                        style={{ accentColor: "var(--brand-600)", width: 18, height: 18, flexShrink: 0 }}
                      />
                      {newQuestion.optionImageFiles[i] ? (
                        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flex: 1 }}>
                          <PendingImagePreview file={newQuestion.optionImageFiles[i]!} maxHeight={60} />
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              setNewQuestion((prev) => {
                                const optionImageFiles = [...prev.optionImageFiles];
                                optionImageFiles[i] = null;
                                return { ...prev, optionImageFiles };
                              })
                            }
                          >
                            {t("review.revertToText")}
                          </Button>
                        </div>
                      ) : (
                        <div style={{ flex: 1 }}>
                          <RichTextEditor
                            compact
                            // remounts when a slot is added/removed so each editor
                            // re-reads its own (shifted) text from state
                            key={`new-option-${formKey}-${newQuestion.options.length}-${i}`}
                            value={text}
                            placeholder={`${t("review.optionPlaceholder")} ${String.fromCharCode(65 + i)}`}
                            onChange={(v) =>
                              setNewQuestion((prev) => {
                                const options = [...prev.options];
                                options[i] = v;
                                return { ...prev, options };
                              })
                            }
                            onPasteImage={(file) => setNewOptionImage(i, file)}
                          />
                        </div>
                      )}
                      {newQuestion.options.length > 2 && (
                        <Button variant="ghost" size="sm" onClick={() => removeOptionSlot(i)}>
                          {t("review.removeOption")}
                        </Button>
                      )}
                    </div>
                  ))}
                  {newQuestion.options.length < MAX_NEW_OPTIONS && (
                    <Button type="button" variant="ghost" size="sm" onClick={addOptionSlot}>
                      + {t("review.addOption")}
                    </Button>
                  )}
                </>
              )}
              <Button type="submit" variant="secondary">
                {t("review.addQuestionSubmit")}
              </Button>
            </form>
          </Card>
        )}

        {canPublish ? (
          <Button size="lg" block onClick={handlePublish} disabled={locked || exam.needs_review_count > 0}>
            {t("review.publish")}
          </Button>
        ) : (
          <p className="body-sm ink-muted">{t("review.alreadyPublished")}</p>
        )}
      </div>

      <Modal open={duplicateOpen} onClose={() => setDuplicateOpen(false)} title={t("review.duplicateTitle")}>
        {duplicateResult ? (
          <div className="stack">
            <p className="body-sm" style={{ color: "var(--success)" }}>
              {t("review.duplicateSuccess", { count: duplicateResult.length })}
            </p>
            <div className="row-stack">
              {duplicateResult.map((created) => (
                <Link
                  key={created.id}
                  to={`/admin/exams/${created.id}/review`}
                  className="body-sm"
                  onClick={() => setDuplicateOpen(false)}
                >
                  {created.class_name} — {created.title}
                </Link>
              ))}
            </div>
            <Button variant="secondary" onClick={() => setDuplicateOpen(false)}>
              {t("common.close")}
            </Button>
          </div>
        ) : (
          <div className="stack">
            <p className="body-sm ink-muted">{t("review.duplicateHint")}</p>
            {duplicateTargets.length === 0 ? (
              <p className="body-sm ink-muted">{t("review.duplicateNoTargets")}</p>
            ) : (
              <div className="stack" style={{ gap: "var(--space-2)" }}>
                {duplicateTargets.map((target) => (
                  <label
                    key={target.id}
                    className="body-sm"
                    style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedClassIds.has(target.id)}
                      onChange={() => toggleDuplicateTarget(target.id)}
                      style={{ accentColor: "var(--brand-600)" }}
                    />
                    {target.name}
                  </label>
                ))}
              </div>
            )}
            {duplicateError && (
              <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                {duplicateError}
              </p>
            )}
            <Button
              onClick={handleDuplicateSubmit}
              disabled={duplicating || selectedClassIds.size === 0}
            >
              {duplicating ? t("review.duplicating") : t("review.duplicateSubmit")}
            </Button>
          </div>
        )}
      </Modal>
    </AdminLayout>
  );
}
