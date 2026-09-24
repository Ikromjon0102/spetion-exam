"""Lightweight stand-in for the Celery beat schedule (celery_app.py's
beat_schedule) on deployments that skip Redis/Celery entirely for RAM
reasons (see CLAUDE.md's deploy notes). Runs the same two lifecycle-sweep
functions Celery beat would dispatch, directly and in-process, on a plain
timer loop — no broker involved.

This does NOT replace CELERY_EAGER=true, which handles the *other* half of
what Celery normally does here (making POST /admin/uploads' parse_exam_
upload.delay() call run synchronously instead of needing a worker). That
half is request-triggered and already covered without this script. This
script exists only for the two *time*-triggered sweeps, which still need
something to call them on a schedule regardless of eager mode:
  - auto_submit_expired_attempts: force-submits+grades attempts whose
    deadline_at has passed but the student never clicked submit.
  - mark_expired_unstarted: flags students who never started an exam at
    all once its window has closed.
Skipping this script would leave those attempts stuck 'in_progress'/
'not_started' forever — they'd never get graded or show up in rankings.

Usage (run as a long-lived process, e.g. under systemd):
    python -m scripts.run_sweep_loop
"""

import time

from app.tasks.exam_lifecycle_tasks import auto_submit_expired_attempts, mark_expired_unstarted

AUTO_SUBMIT_INTERVAL_SECONDS = 20
MARK_EXPIRED_INTERVAL_SECONDS = 60


def main() -> None:
    last_mark_expired = 0.0
    while True:
        start = time.monotonic()
        try:
            auto_submit_expired_attempts()
        except Exception as exc:  # noqa: BLE001 - must never kill the loop
            print(f"[run_sweep_loop] auto_submit_expired_attempts failed: {exc}", flush=True)

        if start - last_mark_expired >= MARK_EXPIRED_INTERVAL_SECONDS:
            try:
                mark_expired_unstarted()
            except Exception as exc:  # noqa: BLE001
                print(f"[run_sweep_loop] mark_expired_unstarted failed: {exc}", flush=True)
            last_mark_expired = start

        elapsed = time.monotonic() - start
        time.sleep(max(0.0, AUTO_SUBMIT_INTERVAL_SECONDS - elapsed))


if __name__ == "__main__":
    main()
