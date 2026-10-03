import { Button } from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";
import type { GuardOverlay } from "../../hooks/useExamGuard";
import "./examguard.css";

interface Props {
  kind: GuardOverlay;
  warnings: number;
  onResume: () => void;
}

/** Opaque, full-viewport cover shown over the questions while the student is
 * outside the exam window (or before full-screen has been entered). Opaque on
 * purpose: the questions must not stay readable behind it. */
export default function ExamGuardOverlay({ kind, warnings, onResume }: Props) {
  const { t } = useLanguage();
  if (!kind) return null;
  const left = kind === "left";
  return (
    <div className="sp-guard" role="alertdialog" aria-modal="true" aria-labelledby="sp-guard-title">
      <div className="sp-guard__card">
        <h2 id="sp-guard-title" className="h3">
          {left ? t("guard.leftTitle") : t("guard.enterTitle")}
        </h2>
        <p className="body">{left ? t("guard.leftText", { count: warnings }) : t("guard.enterText")}</p>
        <Button size="lg" block onClick={onResume} autoFocus>
          {left ? t("guard.leftButton") : t("guard.enterButton")}
        </Button>
      </div>
    </div>
  );
}
