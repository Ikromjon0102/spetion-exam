import { useEffect } from "react";
import type { ReactNode } from "react";
import Icon from "./Icon";
import "./modal.css";

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

export default function Modal({ open, onClose, title, children }: Props) {
  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="sp-modal-overlay" onClick={onClose}>
      <div className="sp-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="sp-modal__head">
          <h2 className="h4" style={{ margin: 0 }}>
            {title}
          </h2>
          <button type="button" className="sp-modal__close" onClick={onClose} aria-label="Yopish">
            <Icon name="x" size={20} />
          </button>
        </div>
        <div className="sp-modal__body">{children}</div>
      </div>
    </div>
  );
}
