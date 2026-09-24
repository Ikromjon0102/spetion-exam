import { useEffect, useState } from "react";

/**
 * Countdown driven by a server-issued absolute deadline — never a locally
 * computed duration (client clocks/tab-sleep can't be trusted; see
 * docs/spec.md section 3 step 7 and section 6 risk #1). This hook is UX
 * only: correctness is enforced server-side by the Celery beat sweep and by
 * every write endpoint rejecting writes past deadline_at.
 *
 * The caller (ExamTakingPage) re-fetches deadline_at on tab focus and passes
 * the refreshed value back in as `deadlineAt`, which restarts this hook's
 * countdown from the corrected time.
 */
export function useExamTimer(deadlineAt: string, onExpire: () => void) {
  const [remainingMs, setRemainingMs] = useState(() => Date.parse(deadlineAt) - Date.now());

  useEffect(() => {
    const interval = setInterval(() => {
      const remaining = Date.parse(deadlineAt) - Date.now();
      setRemainingMs(remaining);
      if (remaining <= 0) {
        clearInterval(interval);
        onExpire();
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [deadlineAt, onExpire]);

  return remainingMs;
}
