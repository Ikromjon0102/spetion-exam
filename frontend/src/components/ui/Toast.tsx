import { useEffect } from "react";
import Icon from "./Icon";
import "./toast.css";

interface Props {
  kind: "success" | "error";
  text: string;
  onClose: () => void;
  /** Success toasts auto-dismiss; errors stay until closed or replaced. */
  autoDismissMs?: number;
}

/** A fixed-position notice, visible wherever the user is scrolled — the
 * exam editor is a very long page, and a banner at the top of it went
 * unseen by someone working at the bottom. */
export default function Toast({ kind, text, onClose, autoDismissMs }: Props) {
  useEffect(() => {
    if (!autoDismissMs) return;
    const timer = setTimeout(onClose, autoDismissMs);
    return () => clearTimeout(timer);
  }, [text, autoDismissMs, onClose]);

  return (
    <div className={`sp-toast sp-toast--${kind}`} role={kind === "error" ? "alert" : "status"}>
      <span className="sp-toast__text">{text}</span>
      <button type="button" className="sp-toast__close" onClick={onClose} aria-label="Yopish">
        <Icon name="x" size={16} />
      </button>
    </div>
  );
}
