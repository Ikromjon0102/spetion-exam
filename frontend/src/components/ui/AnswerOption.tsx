import type { ReactNode } from "react";
import "./answeroption.css";

interface Props {
  letter: string;
  children: ReactNode;
  selected?: boolean;
  correct?: boolean;
  incorrect?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}

export default function AnswerOption({ letter, children, selected, correct, incorrect, disabled, onClick }: Props) {
  const classes = [
    "sp-option",
    selected ? "sp-option--selected" : "",
    correct ? "sp-option--correct" : "",
    incorrect ? "sp-option--incorrect" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button type="button" className={classes} onClick={onClick} disabled={disabled}>
      <span className="sp-option__letter">{letter}</span>
      <span>{children}</span>
    </button>
  );
}
