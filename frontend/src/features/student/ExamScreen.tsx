/**
 * The exam paper as a student sees it: timer bar, block tabs, the questions,
 * and the question navigator. Purely presentational — it owns no answers and
 * calls no API — so the real exam (ExamTakingPage) and the staff's
 * "O'quvchi ko'zi bilan ko'rish" preview (ExamPreviewPage) render exactly the
 * same thing. Change the student's screen here and the preview follows.
 *
 * Never renders is_correct: the data it is given doesn't carry it.
 */
import { useMemo, useState, type ReactNode } from "react";
import type { AttemptQuestion, ExamSectionInfo } from "../../api/studentApi";
import { AnswerOption, AuthedImage, Badge, Button, Card, LanguageSwitcher, Logo, ThemeToggle } from "../../components/ui";
import RichText from "../../components/ui/RichText";
import { useLanguage } from "../../i18n/LanguageContext";
import { formatPoints } from "../../utils/formatPoints";
import { questionImageUrl } from "../../utils/questionImage";
import "../../components/ui/examtimer.css";
import "../../components/ui/appheader.css";
import "./examtaking.css";

const LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H"];

export type SaveState = "saving" | "error";
export type Answers = Record<number, number | null>;
export type TextAnswers = Record<number, string>;

export function isAnswered(q: AttemptQuestion, answers: Answers, textAnswers: TextAnswers): boolean {
  return q.question_type === "short_answer" ? (textAnswers[q.id] ?? "").trim().length > 0 : answers[q.id] != null;
}

export interface QuestionGroup {
  section: ExamSectionInfo | null;
  questions: AttemptQuestion[];
}

/** The paper block by block (one group holding everything when there are no blocks). */
export function groupQuestions(sections: ExamSectionInfo[], questions: AttemptQuestion[]): QuestionGroup[] {
  if (sections.length === 0) return [{ section: null, questions }];
  return sections.map((section) => ({ section, questions: questions.filter((q) => q.section_id === section.id) }));
}

export function formatClock(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  return `${h > 0 ? `${h}:` : ""}${mm}:${String(s).padStart(2, "0")}`;
}

interface Props {
  title: string;
  userName?: string;
  sections: ExamSectionInfo[];
  questions: AttemptQuestion[];
  answers: Answers;
  textAnswers: TextAnswers;
  saveStates?: Record<number, SaveState>;
  remainingSeconds: number;
  /** answers can't be changed (submitting, or time is up) */
  locked?: boolean;
  submitting?: boolean;
  onSelectOption: (questionId: number, optionId: number) => void;
  onChangeText: (questionId: number, text: string) => void;
  onBlurText?: (questionId: number) => void;
  onSubmitClick: () => void;
  /** banners shown above the questions (unsaved answers, preview notice, ...) */
  notices?: ReactNode;
  /** extra controls in the top bar (the preview's "back to editing") */
  headerExtra?: ReactNode;
}

export default function ExamScreen({
  title,
  userName,
  sections,
  questions,
  answers,
  textAnswers,
  saveStates = {},
  remainingSeconds,
  locked = false,
  submitting = false,
  onSelectOption,
  onChangeText,
  onBlurText,
  onSubmitClick,
  notices,
  headerExtra,
}: Props) {
  const { t } = useLanguage();
  const [activeSectionId, setActiveSectionId] = useState<number | null>(sections[0]?.id ?? null);
  const [navOpen, setNavOpen] = useState(false);

  const groups = useMemo(() => groupQuestions(sections, questions), [sections, questions]);
  const numberOf = useMemo(() => {
    const map = new Map<number, number>();
    questions.forEach((q, i) => map.set(q.id, i + 1));
    return map;
  }, [questions]);
  const answered = (q: AttemptQuestion) => isAnswered(q, answers, textAnswers);

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

  const timerClass = remainingSeconds <= 60 ? "sp-timer--danger" : remainingSeconds <= 300 ? "sp-timer--warning" : "";
  const total = questions.length;
  const answeredCount = questions.filter(answered).length;
  const hasSections = sections.length > 0;
  const currentSectionId = hasSections ? activeSectionId ?? sections[0].id : null;
  const visibleGroups = hasSections ? groups.filter((g) => g.section?.id === currentSectionId) : groups;
  const activeIndex = sections.findIndex((s) => s.id === currentSectionId);
  const nextSection = hasSections && activeIndex >= 0 ? sections[activeIndex + 1] : undefined;

  const navigator = (
    <div className="sp-qnav">
      {groups.map((group) => (
        <div key={group.section?.id ?? "all"} className="sp-qnav__group">
          {group.section && (
            <div className="sp-qnav__title">
              <span>{group.section.subject_name}</span>
              <span className="data-sub">
                {group.questions.filter(answered).length}/{group.questions.length}
              </span>
            </div>
          )}
          <div className="sp-qnav__grid">
            {group.questions.map((q) => {
              const classes = [
                "sp-qnav__cell",
                answered(q) ? "sp-qnav__cell--answered" : "",
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
      ))}
      <div className="sp-qnav__legend caption">
        <span>
          <i className="sp-qnav__swatch sp-qnav__swatch--answered" /> {t("taking.legendAnswered")}
        </span>
        <span>
          <i className="sp-qnav__swatch" /> {t("taking.legendBlank")}
        </span>
      </div>
      <Button block onClick={onSubmitClick} disabled={locked}>
        {t("taking.submit")}
      </Button>
    </div>
  );

  return (
    <>
      <header className="sp-header">
        <div className="sp-header__inner sp-exam-header">
          {/* No links here on purpose: leaving this page mid-exam costs time. */}
          <Logo variant="horizontal" tone="red" height={22} />
          <div className="sp-header__user">
            {headerExtra}
            <LanguageSwitcher compact />
            <ThemeToggle />
            {userName && <span className="body-sm ink-muted sp-header__name">{userName}</span>}
          </div>
        </div>
      </header>

      <div className="sp-exam">
        <div className="sp-exam__main">
          <div className={`sp-timer sp-exam__bar ${timerClass}`}>
            <div>
              <div className="data-eyebrow">{t("taking.timeLeft")}</div>
              <div className="sp-timer__value">{formatClock(remainingSeconds)}</div>
            </div>
            <div className="sp-exam__bar-right">
              <div className="caption sp-exam__title" title={title}>
                {title}
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
                    aria-selected={g.section.id === currentSectionId}
                    className={`sp-exam__tab${g.section.id === currentSectionId ? " sp-exam__tab--active" : ""}`}
                    onClick={() => goToSection(g.section!.id)}
                  >
                    {g.section.subject_name}
                    <span className="sp-exam__tab-count">
                      {g.questions.filter(answered).length}/{g.questions.length}
                    </span>
                  </button>
                ) : null
              )}
            </div>
          )}

          {navOpen && <div className="sp-exam__nav-drawer">{navigator}</div>}

          {notices}

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
                        onChange={(e) => onChangeText(q.id, e.target.value)}
                        onBlur={() => onBlurText?.(q.id)}
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
                            onClick={() => onSelectOption(q.id, opt.id)}
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
              <Button size="lg" block onClick={onSubmitClick} disabled={locked}>
                {submitting ? t("taking.submitting") : t("taking.submit")}
              </Button>
            )}
          </div>
        </div>

        <aside className="sp-exam__aside">{navigator}</aside>
      </div>
    </>
  );
}
