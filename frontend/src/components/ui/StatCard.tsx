import type { ReactNode } from "react";
import "./statcard.css";

type Tone = "default" | "danger" | "warning" | "success";

interface Props {
  label: string;
  value: ReactNode;
  tone?: Tone;
}

export default function StatCard({ label, value, tone = "default" }: Props) {
  return (
    <div className="sp-statcard" data-tone={tone}>
      <div className="data-eyebrow sp-statcard__label">{label}</div>
      <div className="sp-statcard__value">{value}</div>
    </div>
  );
}
