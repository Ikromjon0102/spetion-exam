import type { ReactNode } from "react";
import "./badge.css";

export type BadgeStatus = "success" | "warning" | "info" | "danger" | "neutral";

export default function Badge({ status, children }: { status: BadgeStatus; children: ReactNode }) {
  return (
    <span className={`sp-badge sp-badge--${status}`}>
      <span className="sp-badge__dot" />
      {children}
    </span>
  );
}
