import { useCallback, useEffect, useRef, useState } from "react";

// A web page cannot sit above other windows or stop Alt-Tab — browsers forbid
// it on purpose. What it can do, and what this does, is (1) run the exam
// full-screen, (2) notice the student leaving it (full-screen exited, tab or
// window lost focus) and put an opaque warning over the questions until they
// come back, and (3) disable copy / cut / right-click. It is a deterrent on
// school computers, not a lockdown; the server-side deadline stays the only
// authority on time.

export function fullscreenSupported(): boolean {
  return typeof document !== "undefined" && typeof document.documentElement.requestFullscreen === "function";
}

/** Enters full-screen. Browsers only allow this inside a user gesture (a
 * click), so call it straight from a click handler. Never throws: a denied
 * request must not stop the student from taking the exam. */
export async function enterFullscreen(): Promise<void> {
  if (!fullscreenSupported() || document.fullscreenElement) return;
  try {
    await document.documentElement.requestFullscreen();
  } catch {
    // denied or unsupported — carry on windowed
  }
}

export function exitFullscreen(): void {
  if (document.fullscreenElement) document.exitFullscreen().catch(() => undefined);
}

/** "enter": full-screen isn't active yet (e.g. the page was reloaded — a
 * reload always drops it); not counted as a warning. "left": the student
 * left the exam window; counted. */
export type GuardOverlay = "enter" | "left" | null;

export function useExamGuard(active: boolean) {
  const [overlay, setOverlay] = useState<GuardOverlay>(null);
  const [warnings, setWarnings] = useState(0);
  // The ref is what the event handlers read, so a burst of events for one
  // departure (blur + visibilitychange + fullscreenchange all fire together)
  // counts once.
  const overlayRef = useRef<GuardOverlay>(null);

  const show = useCallback((kind: "enter" | "left") => {
    overlayRef.current = kind;
    setOverlay(kind);
  }, []);

  const hide = useCallback(() => {
    overlayRef.current = null;
    setOverlay(null);
  }, []);

  useEffect(() => {
    if (!active) {
      hide();
      return;
    }

    if (fullscreenSupported() && !document.fullscreenElement) show("enter");

    function leave() {
      if (overlayRef.current !== null) return;
      setWarnings((n) => n + 1);
      show("left");
    }
    function onFullscreenChange() {
      if (document.fullscreenElement) {
        if (overlayRef.current === "enter") hide();
        return;
      }
      leave();
    }
    function onVisibility() {
      if (document.visibilityState === "hidden") leave();
    }
    const block = (e: Event) => e.preventDefault();

    document.addEventListener("fullscreenchange", onFullscreenChange);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", leave);
    document.addEventListener("copy", block);
    document.addEventListener("cut", block);
    document.addEventListener("contextmenu", block);
    return () => {
      document.removeEventListener("fullscreenchange", onFullscreenChange);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("blur", leave);
      document.removeEventListener("copy", block);
      document.removeEventListener("cut", block);
      document.removeEventListener("contextmenu", block);
    };
  }, [active, show, hide]);

  /** The overlay's button: ask for full-screen and dismiss the overlay
   * straight away. Deliberately not awaited — a full-screen request can be
   * refused, or in some browsers simply never settle, and a student must never
   * be left stuck behind an overlay while the exam clock runs. */
  const resume = useCallback(() => {
    void enterFullscreen();
    hide();
  }, [hide]);

  return { overlay, warnings, resume };
}
