import { useEffect, useState } from "react";

/** True when the user asked the OS for less motion — every animation here
 * (counting numbers, drawing lines, the morphing radar) is skipped then. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

/** A number that counts up to `target` (ease-out), or just shows it. */
export function useCountUp(target: number | null, enabled: boolean, durationMs = 900): number | null {
  const [value, setValue] = useState<number | null>(enabled ? 0 : target);
  useEffect(() => {
    if (target === null || !enabled) {
      setValue(target);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      setValue(target * (1 - Math.pow(1 - t, 3)));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, enabled, durationMs]);
  return value;
}

/** 0 -> 1 over `durationMs` on demand (the radar's "play" button). */
export function useTween(enabled: boolean) {
  const [t, setT] = useState(1);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const x = Math.min(1, (now - start) / 2600);
      setT(x);
      if (x < 1) frame = requestAnimationFrame(tick);
      else setPlaying(false);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing]);
  return {
    t,
    setT,
    playing,
    play: () => {
      if (!enabled) return setT(1);
      setT(0);
      setPlaying(true);
    },
  };
}
