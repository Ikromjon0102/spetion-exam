import type { ReactNode } from "react";
import "./statcard.css";

type Tone = "default" | "danger" | "warning" | "success";

interface Props {
  label: string;
  value: ReactNode;
  tone?: Tone;
  onClick?: () => void;
}

export default function StatCard({ label, value, tone = "default", onClick }: Props) {
  const content = (
    <>
      <div className="data-eyebrow sp-statcard__label">{label}</div>
      <div className="sp-statcard__value">{value}</div>
    </>
  );

  if (onClick) {
    return (
      <button type="button" className="sp-statcard sp-statcard--clickable" data-tone={tone} onClick={onClick}>
        {content}
      </button>
    );
  }

  return (
    <div className="sp-statcard" data-tone={tone}>
      {content}
    </div>
  );
}
