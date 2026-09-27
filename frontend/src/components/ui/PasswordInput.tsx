import { useState } from "react";
import type { InputHTMLAttributes } from "react";
import Icon from "./Icon";
import "./passwordinput.css";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & { className?: string };

/** Drop-in replacement for <input type="password" className="sp-input" />
 * with a show/hide eye toggle — used everywhere a password is entered
 * (login forms, change-password, admin-created accounts) so a user isn't
 * stuck guessing whether they typed it correctly. */
export default function PasswordInput({ className, ...rest }: Props) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="sp-password-field">
      <input {...rest} type={visible ? "text" : "password"} className={`sp-input ${className ?? ""}`} />
      <button
        type="button"
        className="sp-password-field__toggle"
        tabIndex={-1}
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Parolni yashirish" : "Parolni ko'rsatish"}
      >
        <Icon name={visible ? "eye-off" : "eye"} size={18} />
      </button>
    </div>
  );
}
