import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  addQuestion,
  clearOptionImage,
  clearQuestionPromptImage,
  closeExam,
  deleteExam,
  deleteQuestion,
  duplicateExam,
  getExamDetail,
  getUploadStatus,
  listAdminClasses,
  listMyAssignments,
  publishExam,
  questionImageUrl,
  setOptionImage,
  setQuestionPromptImage,
  setSectionReady,
  updateExam,
  updateQuestion,
  updateQuestionOption,
  uploadSectionFile,
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
import { formatPoints } from "../../utils/formatPoints";
import "../student/examtaking.css";
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

  // Chorak exam: which block is open. A block's teacher lands on their own.
  const [activeSectionId, setActiveSectionId] = useState<number | null>(null);
  const [importingSectionId, setImportingSectionId] = useState<number | null>(null);
  const [titleDraft, setTitleDraft] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
  const isChorak = exam.exam_type === "chorak";
  // Exam-wide actions (schedule, publish, delete, copy): on a chorak exam the
  // admin's alone; a block's teacher only writes their own block.
  const canAdminister = exam.can_administer;
  const activeSection = isChorak
    ? exam.sections.find((s) => s.id === activeSectionId) ?? exam.sections.find((s) => s.can_edit) ?? exam.sections[0] ?? null
    : null;
  const visibleQuestions = isChorak ? exam.questions.filter((q) => q.section_id === activeSection?.id) : exam.questions;
  const pendingQuestions = visibleQuestions.filter((q) => q.needs_review);
  // May the questions on screen be changed: nobody has started, and (chorak)
  // the open block is one of the user's own.
  const questionsLocked = locked || (isChorak && !activeSection?.can_edit);
  const scheduleLocked = locked || !canAdminister;

  // Why "Nashr qilish" can't be pressed yet — said out loud next to the
  // button instead of leaving a greyed-out button to be guessed at.
  const publishBlockers: string[] = [];
  if (canPublish) {
    if (exam.question_count === 0) publishBlockers.push(t("review.blockerNoQuestions"));
    if (exam.needs_review_count > 0) {
      publishBlockers.push(t("review.blockerNeedsReview", { count: exam.needs_review_count }));
    }
    if (isChorak) {
      exam.sections
        .filter((s) => !s.is_ready)
        .forEach((s) =>
          publishBlockers.push(
            t("review.blockerBlockNotReady", { name: s.subject_name, actual: s.actual_count, expected: s.question_count })
          )
        );
    }
    if (!exam.start_at || !exam.end_at) publishBlockers.push(t("review.blockerNoSchedule"));
    else if (new Date(exam.end_at) <= new Date(exam.start_at)) publishBlockers.push(t("schedule.endBeforeStart"));
    else if ((new Date(exam.end_at).getTime() - new Date(exam.start_at).getTime()) / 60000 < exam.duration_minutes) {
      publishBlockers.push(t("schedule.windowTooShort", { minutes: exam.duration_minutes }));
    }
  }

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
        section_id: exam?.exam_type === "chorak" ? currentSectionId() : undefined,
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
      notify(t("review.questionAdded", { count: visibleQuestions.length + 1 }));
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  function currentSectionId(): number | null {
    if (!exam) return null;
    return (
      exam.sections.find((s) => s.id === activeSectionId) ??
      exam.sections.find((s) => s.can_edit) ??
      exam.sections[0]
    )?.id ?? null;
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

  async function approveAll() {
    if (pendingQuestions.length === 0) return;
    setBusy(true);
    try {
      for (const q of pendingQuestions) await updateQuestion(id, q.id, { needs_review: false });
      await reload();
      notify(t("review.approvedAll", { count: pendingQuestions.length }));
    } catch (e) {
      await reload();
      setError(errorDetail(e, t("review.genericError")));
    } finally {
      setBusy(false);
    }
  }

  function jumpToNextPending() {
    const next = pendingQuestions[0];
    if (next) document.getElementById(`question-${next.id}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  async function toggleSectionReady(sectionId: number, ready: boolean) {
    try {
      await setSectionReady(id, sectionId, ready);
      await reload();
      notify(ready ? t("blocks.markedReady") : t("blocks.markedNotReady"));
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  /** A block's questions from a PDF/DOCX: upload, wait for the parser, reload. */
  async function importSectionFile(sectionId: number, file: File) {
    setImportingSectionId(sectionId);
    try {
      const upload = await uploadSectionFile(id, sectionId, file);
      for (let attemptNo = 0; attemptNo < 90; attemptNo++) {
        const status = await getUploadStatus(upload.id);
        if (status.status === "parsed") {
          await reload();
          setActiveSectionId(sectionId);
          notify(t("blocks.imported"));
          return;
        }
        if (status.status === "parse_failed") {
          setError(status.parse_error ?? t("upload.parseFailed"));
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
      setError(t("upload.statusCheckFailed"));
    } catch (e) {
      setError(errorDetail(e, t("upload.failed")));
    } finally {
      setImportingSectionId(null);
    }
  }

  async function saveTitle() {
    const next = (titleDraft ?? "").trim();
    setTitleDraft(null);
    if (!next || !exam || next === exam.title) return;
    try {
      await updateExam(id, { title: next });
      await reload();
      notify(t("review.saved"));
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
  }

  async function handleClose() {
    try {
      await closeExam(id);
      await reload();
      notify(t("review.closed"));
    } catch (e) {
      setError(errorDetail(e, t("review.genericError")));
    }
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
            flexWrap: "wrap",
            gap: "var(--space-3)",
            marginBottom: "var(--space-1)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap", minWidth: 0 }}>
            {titleDraft !== null ? (
              <input
                className="sp-input"
                style={{ minWidth: 260, fontWeight: 700 }}
                value={titleDraft}
                autoFocus
                aria-label={t("upload.titleLabelRequired")}
                onChange={(e) => setTitleDraft(e.target.value)}
                onBlur={saveTitle}
                onKeyDown={(e) => {
                  if (e.key === "Enter") saveTitle();
                  if (e.key === "Escape") setTitleDraft(null);
                }}
              />
            ) : (
              <h1 className="h2">{exam.title}</h1>
            )}
            {canAdminister && !locked && titleDraft === null && (
              <Button variant="ghost" size="sm" onClick={() => setTitleDraft(exam.title)}>
                {t("review.rename")}
              </Button>
            )}
            <Badge status={statusBadge?.status ?? "neutral"}>{statusBadge ? t(statusBadge.key) : exam.status}</Badge>
            {isChorak && <Badge status="info">{t("examType.chorakShort")}</Badge>}
            {exam.archived_at && <Badge status="neutral">{t("examArchive.tabArchive")}</Badge>}
          </div>
          <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
            {exam.phase !== "draft" && (
              <Button size="sm" onClick={() => navigate(`/admin/exams/${id}/ranking`)}>
                {t("adminExamList.results")}
              </Button>
            )}
            {canAdminister && (
              <Button variant="secondary" size="sm" onClick={openDuplicateModal}>
                {t("review.duplicate")}
              </Button>
            )}
            {canAdminister && (exam.phase === "upcoming" || exam.phase === "live") && (
              <ConfirmButton label={t("review.close")} confirmLabel={t("review.closeConfirm")} onConfirm={handleClose} />
            )}
            {canAdminister && (!locked || isAdmin) && (
              <ConfirmButton
                label={t("common.delete")}
                confirmLabel={t("common.confirmDelete")}
                onConfirm={handleDeleteExam}
              />
            )}
          </div>
        </div>
        <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-6)" }}>
          {isChorak ? exam.class_name : `${exam.subject_name} · ${exam.class_name}`}
          {exam.quarter ? ` · ${t("chorak.quarterN", { n: exam.quarter })}` : ""}
          {exam.total_points ? ` · ${formatPoints(exam.total_points)} ${t("result.points")}` : ""}
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
          <div className="sp-form-row">
            <div className="sp-field" style={{ flex: 1 }}>
              <label className="sp-field__label">{t("review.startAt")}</label>
              <input
                className="sp-input"
                type="datetime-local"
                defaultValue={toLocalInputValue(exam.start_at)}
                disabled={scheduleLocked}
                onBlur={(e) => {
                  // only a real change is saved — tabbing through a field
                  // used to fire a save (and a "Saqlandi") every time
                  if (e.target.value && e.target.value !== toLocalInputValue(exam.start_at)) {
                    saveSchedule({ start_at: new Date(e.target.value).toISOString() });
                  }
                }}
              />
            </div>
            <div className="sp-field" style={{ flex: 1 }}>
              <label className="sp-field__label">{t("review.endAt")}</label>
              <input
                className="sp-input"
                type="datetime-local"
                defaultValue={toLocalInputValue(exam.end_at)}
                disabled={scheduleLocked}
                onBlur={(e) => {
                  if (e.target.value && e.target.value !== toLocalInputValue(exam.end_at)) {
                    saveSchedule({ end_at: new Date(e.target.value).toISOString() });
                  }
                }}
              />
            </div>
            <div className="sp-field" style={{ flex: 1 }}>
              <label className="sp-field__label">{t("review.duration")}</label>
              <input
                className="sp-input"
                type="number"
                min={1}
                defaultValue={exam.duration_minutes}
                disabled={scheduleLocked}
                onBlur={(e) => {
                  const next = Number(e.target.value);
                  if (next > 0 && next !== exam.duration_minutes) saveSchedule({ duration_minutes: next });
                }}
              />
            </div>
          </div>
          <p className="caption">{t("schedule.hint")}</p>
          {isChorak && !canAdminister && <p className="caption">{t("blocks.scheduleByAdmin")}</p>}
        </Card>

        {isChorak && (
          <Card className="stack" style={{ marginBottom: "var(--space-8)" }}>
            <div>
              <h2 className="h4">{t("blocks.title")}</h2>
              <p className="body-sm ink-muted">
                {canAdminister ? t("blocks.hintAdmin") : t("blocks.hintTeacher")}
              </p>
            </div>
            <div className="sp-table-scroll">
              <table className="sp-data-table">
                <thead>
                  <tr>
                    <th className="sp-data-table__text">{t("blocks.subject")}</th>
                    <th className="sp-data-table__text">{t("blocks.teacher")}</th>
                    <th>{t("blocks.questions")}</th>
                    <th>{t("blocks.pointsEach")}</th>
                    <th className="sp-data-table__text">{t("blocks.state")}</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {exam.sections.map((section) => {
                    const full = section.actual_count === section.question_count;
                    return (
                      <tr key={section.id}>
                        <td className="sp-data-table__text">
                          {section.subject_name}
                          <span className="sp-block-table__kind">{t(`blocks.kind.${section.kind}`)}</span>
                        </td>
                        <td className="sp-data-table__text" style={{ fontWeight: 400 }}>
                          {section.teacher_names.length > 0 ? (
                            section.teacher_names.join(", ")
                          ) : (
                            <span style={{ color: "var(--warning)" }}>{t("blocks.noTeacher")}</span>
                          )}
                        </td>
                        <td style={{ color: full ? undefined : "var(--warning)" }}>
                          {section.actual_count}/{section.question_count}
                        </td>
                        <td>{formatPoints(section.points_per_question)}</td>
                        <td className="sp-data-table__text">
                          {section.is_ready ? (
                            <Badge status="success">{t("blocks.ready")}</Badge>
                          ) : section.needs_review_count > 0 ? (
                            <Badge status="warning">
                              {t("blocks.pendingReview", { count: section.needs_review_count })}
                            </Badge>
                          ) : (
                            <Badge status="neutral">{t("blocks.inProgress")}</Badge>
                          )}
                        </td>
                        <td>
                          {section.can_edit && (
                            <Button
                              size="sm"
                              variant={section.id === activeSection?.id ? "secondary" : "ghost"}
                              onClick={() => setActiveSectionId(section.id)}
                            >
                              {section.id === activeSection?.id ? t("blocks.opened") : t("blocks.open")}
                            </Button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-4)" }}>
          <h2 className="h3">
            {activeSection ? `${activeSection.subject_name} — ${t("review.questions").toLowerCase()}` : t("review.questions")}
          </h2>
          <span className="body-sm ink-muted">
            {visibleQuestions.length}
            {activeSection ? `/${activeSection.question_count}` : ""} {t("review.questionsCount")} ·{" "}
            {pendingQuestions.length} {t("review.needsReviewCount")}
          </span>
        </div>
        {activeSection?.can_edit && !locked && canPublish && (
          <div className="sp-block-actions">
            <label className={`sp-btn sp-btn--secondary sp-btn--sm${importingSectionId !== null ? " sp-btn--disabled" : ""}`}>
              {importingSectionId === activeSection.id ? t("upload.parsing") : t("blocks.importFile")}
              <input
                type="file"
                accept=".pdf,.docx"
                hidden
                disabled={importingSectionId !== null}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = "";
                  if (file) void importSectionFile(activeSection.id, file);
                }}
              />
            </label>
            {activeSection.is_ready ? (
              <Button variant="ghost" size="sm" onClick={() => toggleSectionReady(activeSection.id, false)}>
                {t("blocks.unmarkReady")}
              </Button>
            ) : (
              <Button
                size="sm"
                disabled={
                  activeSection.actual_count !== activeSection.question_count || activeSection.needs_review_count > 0
                }
                onClick={() => toggleSectionReady(activeSection.id, true)}
              >
                {t("blocks.markReady")}
              </Button>
            )}
            {!activeSection.is_ready && (
              <span className="caption">
                {activeSection.actual_count !== activeSection.question_count
                  ? t("blocks.needCount", { expected: activeSection.question_count, actual: activeSection.actual_count })
                  : activeSection.needs_review_count > 0
                  ? t("review.blockerNeedsReview", { count: activeSection.needs_review_count })
                  : t("blocks.canMarkReady")}
              </span>
            )}
          </div>
        )}
        {!questionsLocked && pendingQuestions.length > 0 && (
          <div className="sp-review-bar">
            <span className="body-sm">
              <strong>{t("review.blockerNeedsReview", { count: pendingQuestions.length })}</strong> —{" "}
              {t("review.reviewHint")}
            </span>
            <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
              <Button variant="secondary" size="sm" onClick={jumpToNextPending}>
                {t("review.nextPending")}
              </Button>
              <ConfirmButton
                label={t("review.approveAll", { count: pendingQuestions.length })}
                confirmLabel={t("review.approveAllConfirm")}
                onConfirm={approveAll}
                disabled={busy}
              />
            </div>
          </div>
        )}
        {!questionsLocked && (
          <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-4)" }}>
            {t("review.autosaveHint")}
          </p>
        )}
        <div className="sp-field" style={{ maxWidth: 280, marginBottom: "var(--space-4)", display: isChorak ? "none" : undefined }}>
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
        {!isChorak && exam.expected_question_count !== null && exam.question_count !== exam.expected_question_count && (
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
          {visibleQuestions.length === 0 && (
            <p className="body-sm ink-muted">{questionsLocked ? t("blocks.emptyLocked") : t("blocks.emptyEditable")}</p>
          )}
          {visibleQuestions.map((q, idx) => (
            <Card key={q.id} id={`question-${q.id}`} className={q.needs_review ? "sp-question--pending" : undefined}>
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
                  {!questionsLocked && (
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
                    disabled={questionsLocked}
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
                        disabled={questionsLocked}
                        onChange={() => setCorrectOption(q.id, opt.id)}
                        style={{ accentColor: "var(--brand-600)", width: 18, height: 18, flexShrink: 0 }}
                      />
                      {opt.option_image_key ? (
                        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flex: 1 }}>
                          <AuthedImage src={questionImageUrl(opt.option_image_key)} maxHeight={60} />
                          {!questionsLocked && (
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
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap" }}>
                  {/* "Tasdiqlash" replaces the old "Tekshirish kerak" checkbox the
                      teacher had to un-tick on every question: approving is the
                      action, so it is the button. */}
                  {q.needs_review ? (
                    <Button size="sm" disabled={questionsLocked} onClick={() => saveQuestion(q.id, { needs_review: false })}>
                      ✓ {t("review.approve")}
                    </Button>
                  ) : (
                    <span className="body-sm" style={{ color: "var(--success)", fontWeight: 600 }}>
                      ✓ {t("review.approved")}
                      {!questionsLocked && (
                        <button
                          type="button"
                          className="sp-link-button"
                          onClick={() => saveQuestion(q.id, { needs_review: true })}
                        >
                          {t("review.unapprove")}
                        </button>
                      )}
                    </span>
                  )}
                  {isChorak ? (
                    <span className="caption">
                      {formatPoints(q.points)} {t("result.points")}
                    </span>
                  ) : (
                    <label className="caption" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      {t("review.pointsLabel")}
                      <input
                        className="sp-input"
                        type="number"
                        min={0.5}
                        step={0.5}
                        style={{ width: 76, padding: "4px 8px" }}
                        defaultValue={q.points}
                        disabled={questionsLocked}
                        onBlur={(e) => {
                          const next = Number(e.target.value);
                          if (next > 0 && next !== q.points) saveQuestion(q.id, { points: next });
                        }}
                      />
                    </label>
                  )}
                </div>
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
                        disabled={questionsLocked || editing !== null}
                        onClick={() => startEdit(q)}
                      >
                        {t("review.editQuestion")}
                      </Button>
                      <ConfirmButton
                        label={t("review.delete")}
                        confirmLabel={t("common.confirmDelete")}
                        disabled={questionsLocked}
                        onConfirm={() => removeQuestion(q.id)}
                      />
                    </>
                  )}
                </div>
              </CardFoot>
            </Card>
          ))}
        </div>

        {!questionsLocked && (
          <Card style={{ marginBottom: "var(--space-8)" }}>
            <h3 className="h4" style={{ marginBottom: "var(--space-4)" }}>
              {t("review.addQuestion")}
              {activeSection ? ` — ${activeSection.subject_name} (${activeSection.actual_count}/${activeSection.question_count})` : ""}
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

        {!canPublish ? (
          <p className="body-sm ink-muted">{t("review.alreadyPublished")}</p>
        ) : canAdminister ? (
          <>
            {publishBlockers.length > 0 && (
              <div className="sp-review-bar sp-review-bar--stack" role="status">
                <strong className="body-sm">{t("review.publishBlockedTitle")}</strong>
                <ul className="sp-intro-rules body-sm">
                  {publishBlockers.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </div>
            )}
            <Button size="lg" block onClick={handlePublish} disabled={locked || publishBlockers.length > 0}>
              {t("review.publish")}
            </Button>
          </>
        ) : (
          <p className="body-sm ink-muted">{t("blocks.publishByAdmin")}</p>
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
