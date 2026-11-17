import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  createChorakExams,
  getQuarters,
  listAdminClasses,
  listExamTemplates,
  type ClassOut,
  type ExamTemplate,
} from "../../../api/adminApi";
import { AdminLayout, Button, Card, ListRow } from "../../../components/ui";
import { useLanguage } from "../../../i18n/LanguageContext";
import { errorDetail } from "../../../utils/errorDetail";
import { formatPoints } from "../../../utils/formatPoints";
import "../../student/examtaking.css";

// Chorak exams in this block format are sat from the 8th grade up; lower
// grades stay one click away for the day that changes.
const MIN_GRADE = 8;

/** Admin-only: pick a block template and the classes that sit it. One draft
 * exam per class is created; each block is then written by the teacher of
 * that subject in that class, and the admin publishes when all are ready. */
export default function ChorakCreatePage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<ExamTemplate[] | null>(null);
  const [classes, setClasses] = useState<ClassOut[]>([]);
  const [templateId, setTemplateId] = useState<number | "">("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [showAllGrades, setShowAllGrades] = useState(false);
  const [title, setTitle] = useState("");
  const [quarter, setQuarter] = useState<number | "">("");
  const [startAt, setStartAt] = useState("");
  const [endAt, setEndAt] = useState("");
  const [duration, setDuration] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listExamTemplates()
      .then((rows) => {
        setTemplates(rows);
        if (rows.length === 1) setTemplateId(rows[0].id);
      })
      .catch(() => setTemplates([]));
    listAdminClasses().then(setClasses).catch(() => undefined);
    // the chorak being sat is almost always the one we are in
    getQuarters()
      .then((q) => setQuarter((prev) => (prev === "" ? q.current_number : prev)))
      .catch(() => undefined);
  }, []);

  const template = useMemo(() => templates?.find((x) => x.id === templateId) ?? null, [templates, templateId]);
  const visibleClasses = useMemo(
    () =>
      classes
        .filter((c) => showAllGrades || c.grade_level >= MIN_GRADE)
        .sort((a, b) => a.grade_level - b.grade_level || a.display_name.localeCompare(b.display_name)),
    [classes, showAllGrades]
  );

  function toggle(classId: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(classId)) next.delete(classId);
      else next.add(classId);
      return next;
    });
  }

  const effectiveDuration = Number(duration) || template?.duration_minutes || 180;
  const windowTooShort =
    startAt !== "" && endAt !== "" && (new Date(endAt).getTime() - new Date(startAt).getTime()) / 60000 < effectiveDuration;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (templateId === "") return setError(t("chorak.needTemplate"));
    if (selected.size === 0) return setError(t("chorak.needClass"));
    if (!title.trim()) return setError(t("chorak.needTitle"));
    if (windowTooShort) return setError(t("schedule.windowTooShort", { minutes: effectiveDuration }));
    setSubmitting(true);
    try {
      const created = await createChorakExams({
        title: title.trim(),
        template_id: templateId,
        class_ids: Array.from(selected),
        quarter: quarter === "" ? null : quarter,
        start_at: startAt ? new Date(startAt).toISOString() : null,
        end_at: endAt ? new Date(endAt).toISOString() : null,
        duration_minutes: Number(duration) > 0 ? Number(duration) : null,
      });
      if (created.length === 1) {
        navigate(`/admin/exams/${created[0].id}/review`);
      } else {
        navigate("/admin/exams?exam_type=chorak", { state: { flash: t("chorak.created", { count: created.length }) } });
      }
    } catch (err) {
      setError(errorDetail(err, t("upload.failed")));
      setSubmitting(false);
    }
  }

  return (
    <AdminLayout>
      <div className="page" style={{ maxWidth: 760 }}>
        <Link to="/admin/exams" className="body-sm" style={{ display: "inline-block", marginBottom: "var(--space-3)" }}>
          ← {t("adminExamList.title")}
        </Link>
        <h1 className="h2" style={{ marginBottom: "var(--space-1)" }}>
          {t("chorak.createTitle")}
        </h1>
        <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-6)" }}>
          {t("chorak.createSubtitle")}
        </p>

        {templates !== null && templates.length === 0 ? (
          <ListRow
            state="free"
            title={t("templates.empty")}
            subtitle={t("chorak.noTemplateHint")}
            trailing={
              <Button size="sm" onClick={() => navigate("/admin/manage/templates")}>
                {t("templates.title")}
              </Button>
            }
          />
        ) : (
          <form onSubmit={handleSubmit} className="stack">
            <Card className="stack">
              <h2 className="h4">1. {t("chorak.stepTemplate")}</h2>
              <div className="sp-field">
                <select
                  className="sp-select"
                  value={templateId}
                  aria-label={t("chorak.stepTemplate")}
                  onChange={(e) => setTemplateId(e.target.value === "" ? "" : Number(e.target.value))}
                >
                  <option value="">{t("chorak.selectTemplate")}</option>
                  {(templates ?? []).map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.name} — {x.total_questions} {t("blocks.questionsShort")}, {formatPoints(x.total_points)}{" "}
                      {t("result.points")}
                    </option>
                  ))}
                </select>
              </div>
              {template && (
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
                  <tfoot>
                    <tr>
                      <td>{t("blocks.total")}</td>
                      <td>{template.total_questions}</td>
                      <td />
                      <td>{formatPoints(template.total_points)}</td>
                    </tr>
                  </tfoot>
                </table>
              )}
              <p className="caption">
                <Link to="/admin/manage/templates">{t("chorak.manageTemplates")}</Link>
              </p>
            </Card>

            <Card className="stack">
              <div className="sp-page-head" style={{ marginBottom: 0 }}>
                <h2 className="h4">
                  2. {t("chorak.stepClasses")}
                  {selected.size > 0 ? ` (${selected.size})` : ""}
                </h2>
                <Button type="button" variant="ghost" size="sm" onClick={() => setShowAllGrades((v) => !v)}>
                  {showAllGrades ? t("chorak.onlyUpperGrades", { grade: MIN_GRADE }) : t("chorak.allGrades")}
                </Button>
              </div>
              <p className="body-sm ink-muted">{t("chorak.classesHint")}</p>
              <div className="sp-check-grid">
                {visibleClasses.map((c) => (
                  <label key={c.id} className={`sp-check-chip${selected.has(c.id) ? " sp-check-chip--on" : ""}`}>
                    <input type="checkbox" checked={selected.has(c.id)} onChange={() => toggle(c.id)} />
                    {c.display_name}
                  </label>
                ))}
              </div>
            </Card>

            <Card className="stack">
              <h2 className="h4">3. {t("chorak.stepDetails")}</h2>
              <div className="sp-form-row">
                <div className="sp-field" style={{ flex: 3 }}>
                  <label className="sp-field__label">{t("upload.titleLabelRequired")}</label>
                  <input
                    className="sp-input"
                    value={title}
                    placeholder={t("chorak.titlePlaceholder")}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </div>
                <div className="sp-field" style={{ flex: 1 }}>
                  <label className="sp-field__label">{t("chorak.quarter")}</label>
                  <select
                    className="sp-select"
                    value={quarter}
                    onChange={(e) => setQuarter(e.target.value === "" ? "" : Number(e.target.value))}
                  >
                    <option value="">—</option>
                    {[1, 2, 3, 4].map((n) => (
                      <option key={n} value={n}>
                        {t("chorak.quarterN", { n })}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="sp-form-row">
                <div className="sp-field" style={{ flex: 1 }}>
                  <label className="sp-field__label">{t("review.startAt")}</label>
                  <input className="sp-input" type="datetime-local" value={startAt} onChange={(e) => setStartAt(e.target.value)} />
                </div>
                <div className="sp-field" style={{ flex: 1 }}>
                  <label className="sp-field__label">{t("review.endAt")}</label>
                  <input className="sp-input" type="datetime-local" value={endAt} onChange={(e) => setEndAt(e.target.value)} />
                </div>
                <div className="sp-field" style={{ flex: 1 }}>
                  <label className="sp-field__label">{t("review.duration")}</label>
                  <input
                    className="sp-input"
                    type="number"
                    min={1}
                    value={duration}
                    placeholder={String(template?.duration_minutes ?? 180)}
                    onChange={(e) => setDuration(e.target.value)}
                  />
                </div>
              </div>
              <p className="caption">{t("schedule.hint")}</p>
              {windowTooShort && (
                <p role="alert" className="body-sm" style={{ color: "var(--warning)" }}>
                  {t("schedule.windowTooShort", { minutes: effectiveDuration })}
                </p>
              )}
            </Card>

            {error && (
              <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                {error}
              </p>
            )}
            <Button type="submit" size="lg" disabled={submitting}>
              {submitting
                ? t("upload.creatingManual")
                : selected.size > 1
                ? t("chorak.submitMany", { count: selected.size })
                : t("chorak.submit")}
            </Button>
            <p className="caption">{t("chorak.afterCreateHint")}</p>
          </form>
        )}
      </div>
    </AdminLayout>
  );
}
