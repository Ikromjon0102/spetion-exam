/**
 * The most failure-sensitive frontend surface — see CLAUDE.md "Next steps"
 * and docs/spec.md sections 2-3.
 *
 * Never renders is_correct anywhere here — the backend doesn't send it
 * before submission either (see AttemptOption in api/studentApi.ts).
 *
 * Three things this page must never do to a student:
 *   - start the clock by accident: opening the page shows an intro screen;
 *     only the "Boshlash" button calls /start;
 *   - end the exam by accident: "Topshirish" asks first and says how many
 *     questions are still blank;
 *   - lose an answer quietly: every answer is queued, retried until the
 *     server has it, flagged on the question while it hasn't, and flushed
 *     before submitting (typed answers included — they used to be sent only
 *     when the field lost focus, so text being typed as the timer ran out
 *     was gone).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import {
  getExamInfo,
  getMyAttempt,
  startExam,
  submitAnswer,
  submitExam,
  type AttemptQuestion,
  type AttemptState,
  type ExamListItem,
} from "../../api/studentApi";
import { useAuth } from "../../auth/AuthContext";
import { enterFullscreen, exitFullscreen, useExamGuard } from "../../hooks/useExamGuard";
import { useExamTimer } from "../../hooks/useExamTimer";
import ExamGuardOverlay from "./ExamGuardOverlay";
import {
  AnswerOption,
  AppHeader,
  AuthedImage,
  Badge,
  Button,
  Card,
  LanguageSwitcher,
  Logo,
  Modal,
  ThemeToggle,
  Toast,
} from "../../components/ui";
import RichText from "../../components/ui/RichText";
import { useLanguage } from "../../i18n/LanguageContext";
import { formatDateTimeUz } from "../../utils/formatDate";
import { formatPoints } from "../../utils/formatPoints";
import { questionImageUrl } from "../../utils/questionImage";
import "../../components/ui/examtimer.css";
import "./examtaking.css";

const FAR_FUTURE = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
const LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H"];
const TEXT_SAVE_DELAY_MS = 1200;
const RETRY_EVERY_MS = 5000;
const FLUSH_TIMEOUT_MS = 6000;

type AnswerPayload = { selected_option_id?: number | null; answer_text?: string | null };
type SaveState = "saving" | "error";

function isFinished(status: string | null | undefined): boolean {
  return status === "submitted" || status === "auto_submitted";
}

function formatClock(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  return `${h > 0 ? `${h}:` : ""}${mm}:${String(s).padStart(2, "0")}`;
}

export default function ExamTakingPage() {
  const { examId } = useParams();
  const id = Number(examId);
  const navigate = useNavigate();
  const { t } = useLanguage();
  const { user } = useAuth();

  const [info, setInfo] = useState<ExamListItem | null>(null);
  const [attempt, setAttempt] = useState<AttemptState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const [answers, setAnswers] = useState<Record<number, number | null>>({});
  const [textAnswers, setTextAnswers] = useState<Record<number, string>>({});
  const [saveStates, setSaveStates] = useState<Record<number, SaveState>>({});
  const [toast, setToast] = useState<string | null>(null);

  const [activeSectionId, setActiveSectionId] = useState<number | null>(null);
  const [navOpen, setNavOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  // The clock ran out but our own /submit didn't get through: the server's
  // sweep submits the attempt by itself within seconds, so wait for it.
  const [waitingForServer, setWaitingForServer] = useState(false);

  const submittedRef = useRef(false);
  // The newest answer per question that the server has not confirmed yet.
  const queue = useRef(new Map<number, AnswerPayload>());
  const inflight = useRef(new Map<number, Promise<void>>());
  const textTimers = useRef(new Map<number, ReturnType<typeof setTimeout>>());
  const stopSaving = useRef(false);

  function applyState(state: AttemptState) {
    setAttempt(state);
    const initial: Record<number, number | null> = {};
    const initialText: Record<number, string> = {};
    state.questions.forEach((q) => {
      initial[q.id] = q.selected_option_id;
      initialText[q.id] = q.answer_text ?? "";
    });
    setAnswers(initial);
    setTextAnswers(initialText);
    setActiveSectionId(state.sections[0]?.id ?? null);
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const examInfo = await getExamInfo(id);
        if (cancelled) return;
        setInfo(examInfo);
        if (examInfo.my_attempt_status === "in_progress") {
          const state = await getMyAttempt(id);
          if (!cancelled) applyState(state);
        }
      } catch {
        if (!cancelled) setLoadError(t("taking.startError"));
      }
    }
    load();

    // Coming back to the tab: the device may have slept, so re-read the
    // server's deadline. Only the deadline — the answers on screen are
    // newer than the server's while a save is still on its way.
    async function onVisible() {
      if (document.visibilityState !== "visible") return;
      try {
        const state = await getMyAttempt(id);
        if (!cancelled) setAttempt((prev) => (prev ? { ...prev, deadline_at: state.deadline_at } : prev));
      } catch {
        // not started yet, or already submitted — nothing to resync
      }
    }
    document.addEventListener("visibilitychange", onVisible);

    const timers = textTimers.current;
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisible);
      timers.forEach((timer) => clearTimeout(timer));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // ---- saving answers -----------------------------------------------------

  const markSave = useCallback((questionId: number, state: SaveState | null) => {
    setSaveStates((prev) => {
      if ((prev[questionId] ?? null) === state) return prev;
      const next = { ...prev };
      if (state === null) delete next[questionId];
      else next[questionId] = state;
      return next;
    });
  }, []);

  const send = useCallback(
    (questionId: number): Promise<void> => {
      const payload = queue.current.get(questionId);
      if (!payload || stopSaving.current) return Promise.resolve();
      markSave(questionId, "saving");
      const request = submitAnswer(id, questionId, payload)
        .then(() => {
          // A newer answer may have been queued while this one was in flight.
          if (queue.current.get(questionId) === payload) {
            queue.current.delete(questionId);
            markSave(questionId, null);
          }
        })
        .catch((e: unknown) => {
          const status = (e as { response?: { status?: number } })?.response?.status;
          if (status === 403 || status === 409) {
            // Time is up or the attempt is closed: retrying can't help.
            stopSaving.current = true;
          }
          markSave(questionId, "error");
          setToast(t("taking.answerSaveError"));
        })
        .finally(() => {
          if (inflight.current.get(questionId) === request) inflight.current.delete(questionId);
        });
      inflight.current.set(questionId, request);
      return request;
    },
    [id, markSave, t]
  );

  // Anything the server hasn't confirmed is retried by itself.
  useEffect(() => {
    if (!attempt) return;
    const interval = setInterval(() => {
      queue.current.forEach((_payload, questionId) => {
        if (!inflight.current.has(questionId) && !textTimers.current.has(questionId)) void send(questionId);
      });
    }, RETRY_EVERY_MS);
    return () => clearInterval(interval);
  }, [attempt, send]);

  /** Sends everything still waiting (typed text included) and waits for it,
   * but never for long: submitting must not hang on a dead connection. */
  const flushAll = useCallback(async () => {
    textTimers.current.forEach((timer) => clearTimeout(timer));
    textTimers.current.clear();
    const pending: Promise<void>[] = [];
    queue.current.forEach((_payload, questionId) => {
      pending.push(inflight.current.get(questionId) ?? send(questionId));
    });
    if (pending.length === 0) return;
    await Promise.race([
      Promise.allSettled(pending),
      new Promise((resolve) => setTimeout(resolve, FLUSH_TIMEOUT_MS)),
    ]);
  }, [send]);

  function selectOption(questionId: number, optionId: number) {
    setAnswers((prev) => ({ ...prev, [questionId]: optionId }));
    queue.current.set(questionId, { selected_option_id: optionId });
    void send(questionId);
  }

  function changeText(questionId: number, text: string) {
    setTextAnswers((prev) => ({ ...prev, [questionId]: text }));
    queue.current.set(questionId, { answer_text: text });
    const existing = textTimers.current.get(questionId);
    if (existing) clearTimeout(existing);
    textTimers.current.set(
      questionId,
      setTimeout(() => {
        textTimers.current.delete(questionId);
        void send(questionId);
      }, TEXT_SAVE_DELAY_MS)
    );
  }

  function blurText(questionId: number) {
    const timer = textTimers.current.get(questionId);
    if (!timer) return;
    clearTimeout(timer);
    textTimers.current.delete(questionId);
    void send(questionId);
  }

  // ---- submitting ---------------------------------------------------------

  const doSubmit = useCallback(
    async (auto: boolean) => {
      if (submittedRef.current || !attempt) return;
      submittedRef.current = true;
      setSubmitting(true);
      setSubmitError(null);
      await flushAll();
      try {
        await submitExam(id);
      } catch {
        // Did it go through anyway (or did the server's own sweep get there
        // first)? Never send the student to a result page that doesn't exist.
        let finished = false;
        try {
          finished = isFinished((await getExamInfo(id)).my_attempt_status);
        } catch {
          // offline — handled below
        }
        if (!finished) {
          submittedRef.current = false;
          setSubmitting(false);
          if (auto) setWaitingForServer(true);
          else setSubmitError(t("taking.submitError"));
          return;
        }
      }
      exitFullscreen();
      navigate(`/student/exams/${id}/result`, { replace: true });
    },
    [attempt, flushAll, id, navigate, t]
  );

  const handleExpire = useCallback(() => {
    setConfirmOpen(false);
    void doSubmit(true);
  }, [doSubmit]);

  const remainingMs = useExamTimer(attempt?.deadline_at ?? FAR_FUTURE, handleExpire);

  // Time ran out and our submit failed: keep asking until the server has
  // closed the attempt (its sweep does that within ~20s of the deadline).
  useEffect(() => {
    if (!waitingForServer) return;
    const interval = setInterval(async () => {
      try {
        await submitExam(id);
      } catch {
        // fall through to the status check
      }
      try {
        if (isFinished((await getExamInfo(id)).my_attempt_status)) {
          exitFullscreen();
          navigate(`/student/exams/${id}/result`, { replace: true });
        }
      } catch {
        // still offline — try again on the next tick
      }
    }, RETRY_EVERY_MS);
    return () => clearInterval(interval);
  }, [waitingForServer, id, navigate]);

  // Full-screen + leave-warning + copy/right-click block, only while there is
  // a live attempt on screen (not on the intro, and not once submitting).
  const guard = useExamGuard(attempt !== null && !submitting && !waitingForServer);

  async function handleStart() {
    setStarting(true);
    setLoadError(null);
    // Full-screen must be requested inside this click (a browser rule). Not
    // awaited: a refused request must never delay the exam.
    void enterFullscreen();
    try {
      applyState(await startExam(id));
    } catch {
      setLoadError(t("taking.startError"));
    } finally {
      setStarting(false);
    }
  }

  // ---- derived ------------------------------------------------------------

  const isAnswered = useCallback(
    (q: AttemptQuestion) =>
      q.question_type === "short_answer" ? (textAnswers[q.id] ?? "").trim().length > 0 : answers[q.id] != null,
    [answers, textAnswers]
  );

  const numberOf = useMemo(() => {
    const map = new Map<number, number>();
    attempt?.questions.forEach((q, i) => map.set(q.id, i + 1));
    return map;
  }, [attempt]);

  const groups = useMemo(() => {
    if (!attempt) return [];
    if (attempt.sections.length === 0) return [{ section: null, questions: attempt.questions }];
    return attempt.sections.map((section) => ({
      section,
      questions: attempt.questions.filter((q) => q.section_id === section.id),
    }));
  }, [attempt]);

  function goToQuestion(q: AttemptQuestion) {
    setActiveSectionId(q.section_id);
    setNavOpen(false);
    // after the (possibly different) block has rendered
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        document.getElementById(`q-${q.id}`)?.scrollIntoView({ block: "start", behavior: "smooth" });
      })
    );
  }

  function goToSection(sectionId: number) {
    setActiveSectionId(sectionId);
    setNavOpen(false);
    requestAnimationFrame(() => window.scrollTo({ top: 0 }));
  }

  // ---- screens ------------------------------------------------------------

  if (loadError && !attempt && !info) {
    return (
      <>
        <AppHeader />
        <div className="page">
          <p role="alert" style={{ color: "var(--danger)", marginBottom: "var(--space-4)" }}>
            {loadError}
          </p>
          <Link to="/student/exams" className="body-sm">
            ← {t("result.backToList")}
          </Link>
        </div>
      </>
    );
  }
  if (!info) {
    return (
      <>
        <AppHeader />
        <div className="page">
          <p className="ink-muted">{t("taking.loading")}</p>
        </div>
      </>
    );
  }
  if (!attempt && isFinished(info.my_attempt_status)) {
    return <Navigate to={`/student/exams/${id}/result`} replace />;
  }

  if (!attempt) {
    const canStart = info.window_state === "active";
    return (
      <>
        <AppHeader />
        <div className="page">
          <p className="data-eyebrow" style={{ marginBottom: "var(--space-2)" }}>
            {info.exam_type === "chorak" ? t("examType.chorak") : info.subject_name}
          </p>
          <h1 className="h2" style={{ marginBottom: "var(--space-6)" }}>
            {info.title}
          </h1>

          <Card className="stack">
            <div className="sp-intro-facts">
              <div>
                <div className="data-eyebrow">{t("intro.duration")}</div>
                <div className="sp-intro-facts__value">
                  {info.duration_minutes} {t("examList.minutes")}
                </div>
              </div>
              <div>
                <div className="data-eyebrow">{t("intro.questions")}</div>
                <div className="sp-intro-facts__value">{info.question_count}</div>
              </div>
              {info.total_points !== null && (
                <div>
                  <div className="data-eyebrow">{t("intro.totalPoints")}</div>
                  <div className="sp-intro-facts__value">{formatPoints(info.total_points)}</div>
                </div>
              )}
            </div>

            {info.sections.length > 0 && (
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
                  {info.sections.map((s) => (
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
            )}

            <ul className="sp-intro-rules body-sm">
              <li>{t("intro.ruleOnce")}</li>
              <li>{t("intro.ruleTimer", { minutes: info.duration_minutes })}</li>
              <li>{t("intro.ruleAutosave")}</li>
              <li>{t("intro.ruleFullscreen")}</li>
            </ul>

            {loadError && (
              <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                {loadError}
              </p>
            )}

            {canStart ? (
              <Button size="lg" block onClick={handleStart} disabled={starting}>
                {starting ? t("taking.loading") : t("intro.start")}
              </Button>
            ) : (
              <p className="body-sm ink-muted">
                {info.window_state === "upcoming"
                  ? `${t("intro.notYet")}${info.start_at ? ` — ${formatDateTimeUz(info.start_at)}` : ""}`
                  : t("intro.closed")}
              </p>
            )}
          </Card>

          <p style={{ marginTop: "var(--space-5)" }}>
            <Link to="/student/exams" className="body-sm">
              ← {t("result.backToList")}
            </Link>
          </p>
        </div>
      </>
    );
  }

  const remainingSeconds = Math.max(0, Math.floor(remainingMs / 1000));
  const timerClass = remainingSeconds <= 60 ? "sp-timer--danger" : remainingSeconds <= 300 ? "sp-timer--warning" : "";
  const total = attempt.questions.length;
  const answeredCount = attempt.questions.filter(isAnswered).length;
  const unsavedCount = Object.values(saveStates).filter((s) => s === "error").length;
  const hasSections = attempt.sections.length > 0;
  const visibleGroups = hasSections ? groups.filter((g) => g.section?.id === activeSectionId) : groups;
  const activeIndex = attempt.sections.findIndex((s) => s.id === activeSectionId);
  const nextSection = hasSections && activeIndex >= 0 ? attempt.sections[activeIndex + 1] : undefined;
  const locked = submitting || waitingForServer;

  const navigator = (
    <div className="sp-qnav">
      {groups.map((group) => {
        const done = group.questions.filter(isAnswered).length;
        return (
          <div key={group.section?.id ?? "all"} className="sp-qnav__group">
            {group.section && (
              <div className="sp-qnav__title">
                <span>{group.section.subject_name}</span>
                <span className="data-sub">
                  {done}/{group.questions.length}
                </span>
              </div>
            )}
            <div className="sp-qnav__grid">
              {group.questions.map((q) => {
                const classes = [
                  "sp-qnav__cell",
                  isAnswered(q) ? "sp-qnav__cell--answered" : "",
                  saveStates[q.id] === "error" ? "sp-qnav__cell--unsaved" : "",
                ]
                  .filter(Boolean)
                  .join(" ");
                return (
                  <button key={q.id} type="button" className={classes} onClick={() => goToQuestion(q)}>
                    {numberOf.get(q.id)}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
      <div className="sp-qnav__legend caption">
        <span>
          <i className="sp-qnav__swatch sp-qnav__swatch--answered" /> {t("taking.legendAnswered")}
        </span>
        <span>
          <i className="sp-qnav__swatch" /> {t("taking.legendBlank")}
        </span>
      </div>
      <Button block onClick={() => setConfirmOpen(true)} disabled={locked}>
        {t("taking.submit")}
      </Button>
    </div>
  );

  const blankBySection = groups
    .map((g) => ({ name: g.section?.subject_name ?? "", blank: g.questions.filter((q) => !isAnswered(q)).length }))
    .filter((g) => g.blank > 0);
  const blankTotal = total - answeredCount;

  return (
    <>
      <header className="sp-header">
        <div className="sp-header__inner sp-exam-header">
          {/* No links here on purpose: leaving this page mid-exam costs time. */}
          <Logo variant="horizontal" tone="red" height={22} />
          <div className="sp-header__user">
            <LanguageSwitcher compact />
            <ThemeToggle />
            <span className="body-sm ink-muted sp-header__name">{user?.full_name}</span>
          </div>
        </div>
      </header>
      <ExamGuardOverlay kind={guard.overlay} warnings={guard.warnings} onResume={guard.resume} />

      <div className="sp-exam">
        <div className="sp-exam__main">
          <div className={`sp-timer sp-exam__bar ${timerClass}`}>
            <div>
              <div className="data-eyebrow">{t("taking.timeLeft")}</div>
              <div className="sp-timer__value">{formatClock(remainingSeconds)}</div>
            </div>
            <div className="sp-exam__bar-right">
              <div className="caption sp-exam__title" title={attempt.exam_title}>
                {attempt.exam_title}
              </div>
              <button type="button" className="sp-exam__progress" onClick={() => setNavOpen((v) => !v)}>
                {answeredCount} / {total} {t("taking.answeredOf")}
                <span className="sp-exam__progress-hint"> · {t("taking.questionsButton")}</span>
              </button>
            </div>
          </div>

          {hasSections && (
            <div className="sp-exam__tabs" role="tablist">
              {groups.map((g) =>
                g.section ? (
                  <button
                    key={g.section.id}
                    type="button"
                    role="tab"
                    aria-selected={g.section.id === activeSectionId}
                    className={`sp-exam__tab${g.section.id === activeSectionId ? " sp-exam__tab--active" : ""}`}
                    onClick={() => goToSection(g.section!.id)}
                  >
                    {g.section.subject_name}
                    <span className="sp-exam__tab-count">
                      {g.questions.filter(isAnswered).length}/{g.questions.length}
                    </span>
                  </button>
                ) : null
              )}
            </div>
          )}

          {navOpen && <div className="sp-exam__nav-drawer">{navigator}</div>}

          {unsavedCount > 0 && (
            <p role="alert" className="sp-exam__unsaved body-sm">
              {t("taking.unsavedBanner", { count: unsavedCount })}
            </p>
          )}
          {waitingForServer && (
            <p role="status" className="sp-exam__unsaved body-sm">
              {t("taking.timeUpWaiting")}
            </p>
          )}

          <div className="stack sp-exam-guarded">
            {visibleGroups.map((group) => (
              <div key={group.section?.id ?? "all"} className="stack">
                {group.section && (
                  <div className="sp-exam__section-head">
                    <h2 className="h4">{group.section.subject_name}</h2>
                    <span className="body-sm ink-muted">
                      {group.questions.length} {t("blocks.questionsShort")} ·{" "}
                      {t("blocks.pointsEachValue", { points: formatPoints(group.section.points_per_question) })}
                    </span>
                  </div>
                )}
                {group.questions.map((q) => (
                  <Card key={q.id} id={`q-${q.id}`} className="sp-exam__question">
                    <div className="sp-exam__question-head">
                      <span className="data-eyebrow">
                        {t("taking.question")} {numberOf.get(q.id)} / {total}
                      </span>
                      {saveStates[q.id] === "error" && <Badge status="danger">{t("taking.notSaved")}</Badge>}
                    </div>
                    {q.prompt_image_key ? (
                      <div style={{ marginBottom: "var(--space-4)" }}>
                        <AuthedImage src={questionImageUrl(q.prompt_image_key)} maxHeight={320} />
                      </div>
                    ) : (
                      <div className="body-lg" style={{ marginBottom: "var(--space-4)" }}>
                        <RichText block text={q.prompt_text} />
                      </div>
                    )}
                    {q.question_type === "short_answer" ? (
                      <textarea
                        className="sp-input"
                        rows={3}
                        disabled={locked}
                        placeholder={t("taking.shortAnswerPlaceholder")}
                        value={textAnswers[q.id] ?? ""}
                        onChange={(e) => changeText(q.id, e.target.value)}
                        onBlur={() => blurText(q.id)}
                        style={{ resize: "vertical" }}
                      />
                    ) : (
                      <div className="stack" style={{ gap: "var(--space-2)" }}>
                        {q.options.map((opt, optIdx) => (
                          <AnswerOption
                            key={opt.id}
                            letter={LETTERS[optIdx] ?? String(optIdx + 1)}
                            selected={answers[q.id] === opt.id}
                            disabled={locked}
                            onClick={() => selectOption(q.id, opt.id)}
                          >
                            {opt.option_image_key ? (
                              <AuthedImage src={questionImageUrl(opt.option_image_key)} maxHeight={80} />
                            ) : (
                              <RichText text={opt.option_text} />
                            )}
                          </AnswerOption>
                        ))}
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            ))}
          </div>

          <div className="sp-exam__footer">
            {nextSection ? (
              <Button size="lg" block variant="secondary" onClick={() => goToSection(nextSection.id)}>
                {t("taking.nextBlock", { name: nextSection.subject_name })} →
              </Button>
            ) : (
              <Button size="lg" block onClick={() => setConfirmOpen(true)} disabled={locked}>
                {submitting ? t("taking.submitting") : t("taking.submit")}
              </Button>
            )}
          </div>
        </div>

        <aside className="sp-exam__aside">{navigator}</aside>
      </div>

      <Modal open={confirmOpen} onClose={() => !submitting && setConfirmOpen(false)} title={t("taking.confirmTitle")}>
        <div className="stack">
          {blankTotal > 0 ? (
            <>
              <p className="body" style={{ color: "var(--warning)", fontWeight: 600 }}>
                {t("taking.confirmBlank", { count: blankTotal, total })}
              </p>
              {hasSections && (
                <ul className="sp-intro-rules body-sm">
                  {blankBySection.map((g) => (
                    <li key={g.name}>
                      {g.name}: {t("taking.confirmBlankInBlock", { count: g.blank })}
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="body">{t("taking.confirmAllAnswered", { total })}</p>
          )}
          <p className="body-sm ink-muted">{t("taking.confirmFinal")}</p>
          {submitError && (
            <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
              {submitError}
            </p>
          )}
          <div className="sp-exam__confirm-actions">
            <Button variant="secondary" onClick={() => setConfirmOpen(false)} disabled={submitting}>
              {t("taking.confirmBack")}
            </Button>
            <Button onClick={() => void doSubmit(false)} disabled={submitting}>
              {submitting ? t("taking.submitting") : submitError ? t("taking.submitRetry") : t("taking.confirmSubmit")}
            </Button>
          </div>
        </div>
      </Modal>

      {toast && <Toast kind="error" text={toast} onClose={() => setToast(null)} autoDismissMs={6000} />}
    </>
  );
}
