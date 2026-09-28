import Icon from "./Icon";
import "./emptystate.css";

interface Props {
  icon: "search" | "inbox";
  title: string;
  subtitle?: string;
}

/** A plain muted sentence reads as "unfinished" more than "nothing here yet"
 * — this pairs it with a small icon so an empty list/search still looks
 * like a deliberate state, not a missing one. */
export default function EmptyState({ icon, title, subtitle }: Props) {
  return (
    <div className="sp-empty-state">
      <div className="sp-empty-state__icon">
        <Icon name={icon} size={20} />
      </div>
      <p className="body-sm" style={{ margin: 0 }}>
        {title}
      </p>
      {subtitle && (
        <p className="body-sm ink-muted" style={{ margin: 0 }}>
          {subtitle}
        </p>
      )}
    </div>
  );
}
