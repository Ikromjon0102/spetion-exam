import { useEffect, useState } from "react";
import Button from "./Button";

interface Props {
  label: string;
  confirmLabel: string;
  onConfirm: () => void;
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
}

/** A destructive action button that arms on first click (label flips to
 * confirmLabel, tone flips to danger) and only fires onConfirm on the
 * second click within a few seconds — no native window.confirm(), which
 * doesn't fire in this project's in-app browser test environment and
 * doesn't match the rest of the design system anyway. */
export default function ConfirmButton({ label, confirmLabel, onConfirm, size = "sm", disabled }: Props) {
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!confirming) return;
    const timer = setTimeout(() => setConfirming(false), 4000);
    return () => clearTimeout(timer);
  }, [confirming]);

  return (
    <Button
      type="button"
      variant={confirming ? "danger" : "ghost"}
      size={size}
      disabled={disabled}
      onClick={(e) => {
        e.stopPropagation();
        if (!confirming) {
          setConfirming(true);
          return;
        }
        setConfirming(false);
        onConfirm();
      }}
    >
      {confirming ? confirmLabel : label}
    </Button>
  );
}
