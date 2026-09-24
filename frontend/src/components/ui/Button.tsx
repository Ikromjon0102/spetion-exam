import type { ButtonHTMLAttributes } from "react";
import "./button.css";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  block?: boolean;
}

export default function Button({
  variant = "primary",
  size = "md",
  block = false,
  className,
  disabled,
  ...rest
}: Props) {
  const classes = [
    "sp-btn",
    `sp-btn--${variant}`,
    size !== "md" ? `sp-btn--${size}` : "",
    block ? "sp-btn--block" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  return <button className={classes} disabled={disabled} aria-disabled={disabled} {...rest} />;
}
