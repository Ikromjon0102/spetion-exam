import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import {
  archiveExams,
  archiveOldExams,
  deleteExam,
  getExamsSummary,
  listExamsPage,
  restoreExams,
  type ExamBulkResult,
  type ExamPhase,
  type ExamSummary,
  type ExamsSummary,
} from "../../api/adminApi";
import { AdminLayout, Badge, Button, ConfirmButton, ListRow, Modal, Toast, type BadgeStatus } from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";
import { errorDetail } from "../../utils/errorDetail";
import { formatDateUz, formatTimeUz } from "../../utils/formatDate";

const PAGE_SIZE = 50;

const PHASE_BADGE: Record<ExamPhase, { status: BadgeStatus; key: string }> = {
  draft: { status: "neutral", key: "phase.draft" },
  upcoming: { status: "info", key: "phase.upcoming" },
  live: { status: "warning", key: "phase.live" },
  finished: { status: "success", key: "phase.finished" },
};

const PHASES: ExamPhase[] = ["draft", "upcoming", "live", "finished"];

interface Group {
  key: string;
  label: string;
  exams: ExamSummary[];
}

/** An exam day is the unit people think in ("what happened last Saturday"),
 * so the list is grouped by the calendar day an exam starts; drafts, which
 * have no day yet, share one group. Order follows the server's newest-first. */
function groupByDay(exams: ExamSummary[], t: (key: string, params?: Record<string, string | number>) => string): Group[] {
  const groups = new Map<string, Group>();
  for (const exam of exams) {
    const dated = exam.phase !== "draft" && exam.start_at;
    const d = dated ? new Date(exam.start_at as string) : null;
    const key = d ? `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}` : "draft";
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        label: d
          ? `${formatDateUz(exam.start_at as string)} · ${t(`weekday.${d.getDay()}`)}`
          : t("examArchive.groupDrafts"),
        exams: [],
      });
    }
    groups.get(key)!.exams.push(exam);
  }
  return Array.from(groups.values());
}

export default function AdminExamListPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();

  // One-shot confirmation handed over by the page that navigated here (e.g.
  // the editor after publishing) — read once, then cleared from history so
  // a refresh doesn't show it again.
  const [flash, setFlash] = useState<string | null>((location.state as { flash?: string } | null)?.flash ?? null);
  useEffect(() => {
    if (flash) window.history.replaceState({}, "");
  }, [flash]);

  const [archived, setArchived] = useState(false);
  const [subjectId, setSubjectId] = useState<number | null>(null);
  const [classId, setClassId] = useState<number | null>(null);
  const [phase, setPhase] = useState<ExamPhase | "">("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  // Links from the dashboard: ?needsReview=1 and ?status=...
  const [needsReview, setNeedsReview] = useState(searchParams.get("needsReview") === "1");
  const [examStatus, setExamStatus] = useState<string | null>(searchParams.get("status"));

  const [items, setItems] = useState<ExamSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<ExamsSummary | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  // Checkboxes only exist while selecting: always-on checkboxes cluttered
  // every row of a list that is mostly just read.
  const [selectMode, setSelectMode] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [archiveOldOpen, setArchiveOldOpen] = useState(false);
  const [archiveOldDays, setArchiveOldDays] = useState("14");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const filtersKey = JSON.stringify([archived, subjectId, classId, phase, debouncedSearch, needsReview, examStatus]);
  // Guards against a slow earlier response overwriting a newer one.
  const requestId = useRef(0);

  const fetchPage = useCallback(
    async (offset: number) => {
      const mine = ++requestId.current;
      setLoading(true);
      try {
        const page = await listExamsPage({
          archived,
          subject_id: subjectId ?? undefined,
          class_id: classId ?? undefined,
          phase: phase || undefined,
          q: debouncedSearch || undefined,
          needs_review: needsReview || undefined,
          exam_status: examStatus ?? undefined,
          limit: PAGE_SIZE,
          offset,
        });
        if (mine !== requestId.current) return;
        setItems((prev) => (offset === 0 ? page.items : [...prev, ...page.items]));
        setTotal(page.total);
      } catch {
        if (mine === requestId.current) setError(t("adminExamList.loadError"));
      } finally {
        if (mine === requestId.current) setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [filtersKey]
  );

  const refreshSummary = useCallback(() => {
    getExamsSummary(archived)
      .then(setSummary)
      .catch(() => undefined);
  }, [archived]);

  useEffect(() => {
    setSelected(new Set());
    fetchPage(0);
  }, [fetchPage]);

  useEffect(() => {
    refreshSummary();
  }, [refreshSummary]);

  function reload() {
    setSelected(new Set());
    fetchPage(0);
    refreshSummary();
  }

  function endSelecting() {
    setSelectMode(false);
    setSelected(new Set());
  }

  function switchTab(toArchive: boolean) {
    if (toArchive === archived) return;
    endSelecting();
    setArchived(toArchive);
    setSubjectId(null);
    setClassId(null);
    setPhase("");
  }

  function clearFilters() {
    setSubjectId(null);
    setClassId(null);
    setPhase("");
    setSearch("");
    setNeedsReview(false);
    setExamStatus(null);
    setSearchParams({});
  }

  function report(result: ExamBulkResult, doneKey: string) {
    if (result.changed.length === 0) {
      setError(t("examArchive.nothingToArchive"));
      return;
    }
    const skipped = result.skipped.length > 0 ? ` · ${t("examArchive.skippedNote", { count: result.skipped.length })}` : "";
    setMessage(`${t(doneKey, { count: result.changed.length })}${skipped}`);
  }

  async function run(action: () => Promise<ExamBulkResult>, doneKey: string) {
    try {
      report(await action(), doneKey);
      setSelectMode(false);
      reload();
    } catch (e) {
      setError(errorDetail(e, t("examArchive.error")));
    }
  }

  async function handleArchiveOld() {
    const days = Number(archiveOldDays);
    if (!Number.isInteger(days) || days < 1) return;
    setArchiveOldOpen(false);
    await run(() => archiveOldExams(days), "examArchive.archivedToast");
  }

  async function handleDelete(examId: number) {
    try {
      await deleteExam(examId);
      reload();
    } catch (err) {
      setError(errorDetail(err, t("adminExamList.deleteError")));
    }
  }

  function toggle(examId: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(examId)) next.delete(examId);
      else next.add(examId);
      return next;
    });
  }

  function toggleGroup(group: Group) {
    // In the working view only archivable exams can be picked (archiving a
    // running exam is refused anyway); in the archive anything can be restored.
    const ids = group.exams.filter((e) => archived || e.can_archive).map((e) => e.id);
    setSelected((prev) => {
      const next = new Set(prev);
      const allIn = ids.length > 0 && ids.every((id) => next.has(id));
      ids.forEach((id) => (allIn ? next.delete(id) : next.add(id)));
      return next;
    });
  }

  function toggleCollapsed(key: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const groups = useMemo(() => groupByDay(items, t), [items, t]);
  const hasFilter = subjectId !== null || classId !== null || phase !== "" || search !== "" || needsReview || examStatus !== null;
  const selectedIds = Array.from(selected);

  return (
    <AdminLayout>
      <div className="page">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--space-3)",
            flexWrap: "wrap",
            marginBottom: "var(--space-5)",
          }}
        >
          <h1 className="h2">{t("adminExamList.title")}</h1>
          <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
            <Button
              variant={selectMode ? "primary" : "secondary"}
              size="sm"
              onClick={() => (selectMode ? endSelecting() : setSelectMode(true))}
            >
              {selectMode ? t("examArchive.selectDone") : t("examArchive.selectMode")}
            </Button>
            {!archived && (
              <Button variant="secondary" size="sm" onClick={() => setArchiveOldOpen(true)}>
                {t("examArchive.archiveOld")}
              </Button>
            )}
            <Button size="sm" onClick={() => navigate("/admin/exams/upload")}>
              {t("adminExamList.new")}
            </Button>
          </div>
        </div>

        <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
          <Button variant={archived ? "ghost" : "secondary"} onClick={() => switchTab(false)}>
            {t("examArchive.tabCurrent")}
            {summary ? ` (${summary.current})` : ""}
          </Button>
          <Button variant={archived ? "secondary" : "ghost"} onClick={() => switchTab(true)}>
            {t("examArchive.tabArchive")}
            {summary ? ` (${summary.archived})` : ""}
          </Button>
        </div>

        {summary && summary.subjects.length > 0 && (
          <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap", marginBottom: "var(--space-4)" }}>
            <Button size="sm" variant={subjectId === null ? "secondary" : "ghost"} onClick={() => setSubjectId(null)}>
              {t("examArchive.allSubjects")} ({archived ? summary.archived : summary.current})
            </Button>
            {summary.subjects.map((s) => (
              <Button
                key={s.id}
                size="sm"
                variant={subjectId === s.id ? "secondary" : "ghost"}
                onClick={() => setSubjectId(subjectId === s.id ? null : s.id)}
              >
                {s.name} ({s.count})
              </Button>
            ))}
          </div>
        )}

        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", marginBottom: "var(--space-4)" }}>
          <input
            className="sp-input"
            style={{ maxWidth: 280 }}
            placeholder={t("examArchive.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            className="sp-input"
            style={{ maxWidth: 200 }}
            value={classId ?? ""}
            onChange={(e) => setClassId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">{t("examArchive.allClasses")}</option>
            {summary?.classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.count})
              </option>
            ))}
          </select>
          <select
            className="sp-input"
            style={{ maxWidth: 200 }}
            value={phase}
            onChange={(e) => setPhase(e.target.value as ExamPhase | "")}
          >
            <option value="">{t("examArchive.allPhases")}</option>
            {PHASES.map((p) => (
              <option key={p} value={p}>
                {t(PHASE_BADGE[p].key)}
              </option>
            ))}
          </select>
          {needsReview && <Badge status="danger">{t("adminExamList.filteredNeedsReview")}</Badge>}
          {hasFilter && (
            <button
              type="button"
              className="body-sm"
              style={{ color: "var(--brand-600)", background: "none", border: "none", cursor: "pointer", padding: 0 }}
              onClick={clearFilters}
            >
              {t("examArchive.clearFilters")}
            </button>
          )}
        </div>

        {selectMode && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-3)",
              flexWrap: "wrap",
              padding: "var(--space-3) var(--space-4)",
              marginBottom: "var(--space-4)",
              background: "var(--surface-raised)",
              border: "1.5px solid var(--info)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <span className="body-sm">
              {selectedIds.length > 0
                ? t("examArchive.selected", { count: selectedIds.length })
                : t("examArchive.pickHint")}
            </span>
            {archived ? (
              <Button size="sm" disabled={selectedIds.length === 0} onClick={() => run(() => restoreExams(selectedIds), "examArchive.restoredToast")}>
                {t("examArchive.restore")}
              </Button>
            ) : (
              <Button
                size="sm"
                disabled={selectedIds.length === 0}
                onClick={() => run(() => archiveExams(selectedIds), "examArchive.archivedToast")}
              >
                {t("examArchive.archive")}
              </Button>
            )}
            {selectedIds.length > 0 && (
              <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
                {t("examArchive.clearSelection")}
              </Button>
            )}
          </div>
        )}

        {flash && <Toast kind="success" text={flash} autoDismissMs={4000} onClose={() => setFlash(null)} />}
        {message && <Toast kind="success" text={message} autoDismissMs={5000} onClose={() => setMessage(null)} />}
        {error && <Toast kind="error" text={error} onClose={() => setError(null)} />}

        {!loading && items.length === 0 && !error && (
          <ListRow
            state="free"
            title={archived ? t("examArchive.emptyArchive") : hasFilter ? t("common.noSearchResults") : t("adminExamList.empty")}
            subtitle={!archived && !hasFilter ? t("adminExamList.emptySubtitle") : undefined}
          />
        )}

        <div className="stack">
          {groups.map((group) => {
            const open = !collapsed.has(group.key);
            const pickable = group.exams.filter((e) => archived || e.can_archive);
            const allPicked = pickable.length > 0 && pickable.every((e) => selected.has(e.id));
            return (
              <section key={group.key}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-3)",
                    margin: "var(--space-2) 0",
                  }}
                >
                  {selectMode && pickable.length > 0 && (
                    <input
                      type="checkbox"
                      checked={allPicked}
                      onChange={() => toggleGroup(group)}
                      aria-label={t("examArchive.selectGroup")}
                      title={t("examArchive.selectGroup")}
                      style={{ accentColor: "var(--brand-600)", width: 18, height: 18 }}
                    />
                  )}
                  <button
                    type="button"
                    onClick={() => toggleCollapsed(group.key)}
                    aria-expanded={open}
                    className="h4"
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: 0,
                      color: "inherit",
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-2)",
                    }}
                  >
                    <span aria-hidden="true">{open ? "▾" : "▸"}</span>
                    {group.label}
                    <span className="body-sm ink-muted">{t("examArchive.groupCount", { count: group.exams.length })}</span>
                  </button>
                </div>
                {open && (
                  <div className="row-stack">
                    {group.exams.map((exam) => {
                      const badge = PHASE_BADGE[exam.phase];
                      const canPick = archived || exam.can_archive;
                      return (
                        <div key={exam.id} style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                          {selectMode && (
                            <input
                              type="checkbox"
                              checked={selected.has(exam.id)}
                              disabled={!canPick}
                              onChange={() => toggle(exam.id)}
                              aria-label={exam.title}
                              style={{ accentColor: "var(--brand-600)", width: 18, height: 18, flexShrink: 0 }}
                            />
                          )}
                          <div style={{ flex: 1, minWidth: 0 }}>
                            {/* Row itself isn't clickable: its trailing slot holds
                                real buttons (a clickable ListRow is a <button>, and
                                nested buttons are invalid) — hence the explicit "Ko'rish". */}
                            <ListRow
                              leading={
                                <>
                                  <span className="data-eyebrow">{exam.class_name}</span>
                                  <span className="data-value">{exam.question_count}</span>
                                </>
                              }
                              title={exam.title}
                              subtitle={[
                                exam.subject_name,
                                exam.start_at && exam.phase !== "draft" ? formatTimeUz(exam.start_at) : null,
                                `${exam.duration_minutes} ${t("examList.minutes")}`,
                              ]
                                .filter(Boolean)
                                .join(" · ")}
                              trailing={
                                <>
                                  {exam.needs_review_count > 0 && (
                                    <Badge status="danger">
                                      {exam.needs_review_count} {t("adminExamList.needsReview")}
                                    </Badge>
                                  )}
                                  <Badge status={badge.status}>{t(badge.key)}</Badge>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => navigate(`/admin/exams/${exam.id}/review`)}
                                  >
                                    {t("adminExamList.view")}
                                  </Button>
                                  {archived ? (
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => run(() => restoreExams([exam.id]), "examArchive.restoredToast")}
                                    >
                                      {t("examArchive.restore")}
                                    </Button>
                                  ) : (
                                    exam.can_archive && (
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => run(() => archiveExams([exam.id]), "examArchive.archivedToast")}
                                      >
                                        {t("examArchive.archive")}
                                      </Button>
                                    )
                                  )}
                                  <ConfirmButton
                                    label={t("common.delete")}
                                    confirmLabel={t("common.confirmDelete")}
                                    onConfirm={() => handleDelete(exam.id)}
                                  />
                                </>
                              }
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>
            );
          })}
        </div>

        {items.length < total && (
          <div style={{ marginTop: "var(--space-5)", textAlign: "center" }}>
            <Button variant="secondary" disabled={loading} onClick={() => fetchPage(items.length)}>
              {t("examArchive.loadMore", { shown: items.length, total })}
            </Button>
          </div>
        )}
      </div>

      <Modal open={archiveOldOpen} onClose={() => setArchiveOldOpen(false)} title={t("examArchive.archiveOldTitle")}>
        <div className="stack">
          <p className="body-sm ink-muted">{t("examArchive.archiveOldHint")}</p>
          <div className="sp-field">
            <label className="sp-field__label">{t("examArchive.archiveOldDays")}</label>
            <input
              className="sp-input"
              type="number"
              min={1}
              value={archiveOldDays}
              onChange={(e) => setArchiveOldDays(e.target.value)}
            />
          </div>
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            <Button onClick={handleArchiveOld} disabled={!(Number(archiveOldDays) >= 1)}>
              {t("examArchive.archive")}
            </Button>
            <Button variant="ghost" onClick={() => setArchiveOldOpen(false)}>
              {t("richEditor.cancel")}
            </Button>
          </div>
        </div>
      </Modal>
    </AdminLayout>
  );
}
