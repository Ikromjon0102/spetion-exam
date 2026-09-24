import type { ReactNode } from "react";
import "./listrow.css";

export type RowState = "resting" | "now" | "next" | "free";

interface Props {
  state?: RowState;
  leading?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  trailing?: ReactNode;
  chevron?: boolean;
  onClick?: () => void;
}

export default function ListRow({ state = "resting", leading, title, subtitle, trailing, chevron, onClick }: Props) {
  const classes = ["sp-row", state !== "resting" ? `sp-row--${state}` : ""].filter(Boolean).join(" ");
  const clickable = onClick && state !== "free";

  const content = (
    <>
      {leading && <div className="sp-row__leading">{leading}</div>}
      <div className="sp-row__info">
        <div className="sp-row__title">{title}</div>
        {subtitle && <div className="sp-row__subtitle">{subtitle}</div>}
      </div>
      {(trailing || chevron) && (
        <div className="sp-row__trailing">
          {trailing}
          {chevron && (
            <svg className="sp-row__chevron" width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M6 4l4 4-4 4"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </div>
      )}
    </>
  );

  if (clickable) {
    return (
      <button type="button" className={classes} onClick={onClick}>
        {content}
      </button>
    );
  }
  return <div className={classes}>{content}</div>;
}
