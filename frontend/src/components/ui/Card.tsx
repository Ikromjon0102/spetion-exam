import type { CSSProperties, ReactNode } from "react";
import "./card.css";

export function Card({
  children,
  className,
  style,
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div className={`sp-card ${className ?? ""}`} style={style}>
      {children}
    </div>
  );
}

export function CardHead({ children }: { children: ReactNode }) {
  return <div className="sp-card__head">{children}</div>;
}

export function CardFoot({ children }: { children: ReactNode }) {
  return <div className="sp-card__foot">{children}</div>;
}
