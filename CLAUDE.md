# Spetion Exam Platform — Project Context

This file is read automatically by Claude Code whenever a session opens this
folder. It carries the full spec so you don't need to re-explain the project.

## What this is

A web platform for Spetion School (Uzbekistan). Students pick their class
(sinf), log in with username/password, and take scheduled exams. Teachers/
admins upload exam questions as PDF/DOCX, the system parses them into
structured questions, a teacher reviews/corrects them, schedules an active
window, students take the exam under a server-enforced timer, grading is
automatic, and a per-class ranking is produced. Student profiles track
subject performance over time (not just per-exam).

## Stack (decided, do not change without asking)

- **Backend**: Python, FastAPI (chosen over Django/Flask — async I/O for
  parsing + timer sweep, Pydantic validation, no need for Django's
  templating/admin since the UI is a separate React app).
- **DB**: PostgreSQL.
- **Frontend**: React (Vite + TypeScript).
- **Background jobs**: Celery + Redis — used for (a) PDF/DOCX parsing
  (never inline in the request, it can take seconds), and (b) a beat task
  every 15-30s that force-submits exams whose `deadline_at` has passed.
- **File storage**: S3-compatible (MinIO locally, real S3/equivalent in
  prod) for raw uploaded exam files. Dev-only escape hatch when
  Docker/MinIO/Redis aren't available: `STORAGE_BACKEND=local` +
  `CELERY_EAGER=true` in `.env` (see `app/core/storage.py`,
  `app/tasks/celery_app.py`) — plain disk + synchronous in-process parsing.
  Never the default; never use in prod.
- **i18n**: interface chrome only (buttons/labels/status badges) is
  UZ/RU-switchable via `frontend/src/i18n/` — a flat key→{uz,ru} dictionary
  (`translations.ts`) + `useLanguage()`. Exam *content* (questions,
  answers) is never translated — it stays in whatever language the
  uploading teacher wrote it in. Every new UI string needs a translations.ts
  entry; don't hardcode Uzbek strings in components.
- **Theme**: light/dark via a manual toggle (`frontend/src/theme/
  ThemeContext.tsx`, `data-theme` attr on `<html>`), defaulting to OS
  preference on first load, persisted in localStorage.
- **Teacher-scoped exam authoring UX**: the upload page (`frontend/src/
  features/admin/ExamUploadPage.tsx`) shows a teacher only their own
  `teacher_class_subjects` (class, subject) pairs — a subject dropdown
  (from `GET /admin/teachers/me/assignments`), then a class dropdown
  cascading off the chosen subject — not the whole school's class/subject
  lists. A teacher who teaches two subjects (e.g. Huquq to 10huquq/8huquq
  *and* Tarix to the same two classes) only ever sees their own 4 pairs,
  never classes/subjects that aren't theirs. Admin is unrestricted and
  still gets the old independent full-list pickers — this endpoint returns
  `[]` for admin by design; don't "fix" that into erroring.

## Current status

Backend is implemented end-to-end (78 passing tests in `backend/app/tests/`,
run with `pytest app/tests -q` against an in-memory SQLite DB — no live
Postgres needed to test) and has been exercised live: Node.js + Docker
Desktop were installed into this dev environment, the frontend was built
with `npm run build` (0 TypeScript errors), and the full student flow
(login → shuffled timed exam → autosave → submit → grading → ranking) and
admin flow (login → create exam → add questions → publish →
monitoring/ranking) were driven end-to-end in a real browser against a
running backend + sqlite dev DB seeded from `backend/seed_data/`.

- **Self-service password change**: `POST /auth/change-password`
  (`app/routers/auth.py`) + `frontend/src/features/shared/
  ChangePasswordPage.tsx` (`/change-password`, all roles, linked from
  `AppHeader`). Needed because all 48 seeded teachers share one temp
  password (`Spetion2026!`) — this is how each teacher sets their own.
- **Admin management panel** (`frontend/src/features/admin/manage/`):
  create/list subjects, create/list/edit teachers (toggle active,
  add/remove `teacher_class_subjects` assignments) at `/admin/manage/
  {subjects,teachers}` (admin-only); create/list students at `/admin/manage/
  students` (admin-only, whole-school roster) — `backend/app/routers/
  admin_management.py` + `admin_management.py` schemas. `school_id`/
  `academic_year_id` are never exposed to this UI — v1 is single-tenant/
  single-year, the backend resolves-or-creates "the" school + current
  academic year itself via `_get_or_create_default_context()`.
- **Classes + homeroom teacher ("sinf rahbari")**: `Class.homeroom_teacher_id`
  (nullable FK to `teachers.id`, migration
  `a1c9f3e7b2d4_add_homeroom_teacher_to_classes`) — a class can have one
  teacher assigned as its homeroom. `/classes` (`ClassesPage.tsx`,
  teacher+admin) lists classes — admin sees every class school-wide and can
  create new ones; a teacher sees only classes they're connected to (their
  homeroom, or any class they teach a subject in via
  `teacher_class_subjects`), read from `GET /admin/teachers/me/assignments`
  + `MeOut.homeroom_class_ids` (populated in `auth.py`'s `/me`). Clicking a
  class goes to `/classes/:id` (`ClassDetailPage.tsx`) showing the
  subject→teacher table and student count for anyone with access. The
  roster itself is now visible (read-only) to **any** teacher with view
  access — homeroom *or* just teaching a subject there — not only the
  homeroom teacher; only the roster *management* UI (add/bulk-import/
  reset-password/edit/delete student) is gated on the backend's
  `can_manage_students` flag from `GET /admin/classes/{id}`, true for
  admin always and for a teacher only when they're that class's homeroom.
  (Originally the non-homeroom view showed only a student *count*, no
  names — the user explicitly asked whether a subject teacher could see
  their own students too, so `list_students` was opened up for reads; see
  below.) Admin (only) can reassign homeroom teacher inline via a
  dropdown, `PUT /admin/classes/{id}`.
  Authorization is enforced server-side in `admin_management.py` via two
  helpers: `_ensure_class_view_access` (view: admin, homeroom, or any
  teacher with a `teacher_class_subjects` row for that class — used by
  both `get_class_detail` and, now, `list_students` when a `class_id` is
  given) and `_ensure_class_homeroom` (mutate: admin or that class's
  homeroom only) — every roster-mutating endpoint (`create_student`,
  `update_student`, `bulk_import_students`, `reset_class_passwords`)
  accepts `require_role("admin", "teacher")` and calls
  `_ensure_class_homeroom`; `list_students`' *default* (no `class_id`)
  listing for a teacher is the union of their homeroom classes and every
  class they teach a subject in (not the whole school). A teacher can
  never reassign a student to a different class themselves (only admin
  can) — enforced in `update_student`. Don't loosen the *mutate* checks
  without re-reading `app/tests/test_class_homeroom.py`, the source of
  truth for the exact intended access matrix (view vs. manage are
  deliberately different scopes — confirmed with the user both times: view
  access was widened to "any teacher of the class" after homeroom-only
  editing was already confirmed as the mutate boundary).
- **Bulk student import**: `POST /admin/students/bulk-import` +
  the "Ro'yxatdan ko'p o'quvchi qo'shish" card on the Students page — the
  admin pastes a class roster (one full name per line, straight from an
  Excel column) and picks the class; username, `student_code`, and a
  shared temp password (`Spetion2026!`, same pattern as teachers) are all
  auto-generated server-side, with collisions (duplicate names, a name
  that already has a username) disambiguated with a numeric suffix. This
  is the answer to "how do I enter ~400 students without doing it one by
  one" — the single-student form (`POST /admin/students`) still exists for
  one-off adds. The response returns the generated username/password per
  row so the admin can print/hand them out; it's shown once and not
  persisted anywhere else, so the admin needs to save/print it immediately.
- **Bulk password reset per class**: `POST /admin/classes/{id}/reset-password`
  + the "Sinf bo'yicha parolni almashtirish" card on the Students page —
  sets the same new password on every student currently in that class (e.g.
  give the whole "10huquq" roster the word `huquq2026` instead of resetting
  15 accounts one by one). The frontend confirms with an inline two-step
  button (label flips to "Ha, almashtirish" + a warning line) instead of
  `window.confirm()` — the in-app browser pane used for manual verification
  suppresses native JS dialogs entirely (silently returns `false`), so a
  real `confirm()` call would never fire there; the in-page step also works
  for real users and matches the rest of the design system rather than a
  native browser dialog. Each student can still change their own password
  afterwards via `POST /auth/change-password`.
- **Left sidebar shell for teacher/admin** (`frontend/src/components/ui/
  AdminLayout.tsx` + `adminlayout.css` + `Icon.tsx`): replaces the old
  top `AppHeader` bar for every teacher/admin page (dashboard, exam
  list/upload/review/ranking, classes, subjects, students, teachers).
  Collapsible (chevron button, state in `localStorage["sidebarCollapsed"]`,
  a per-viewer convenience like theme/lang — never assume it's set), and
  auto-collapses to icon-only under 720px width regardless of that stored
  preference. Each former "Boshqaruv" tab (Sinflar/Fanlar/O'quvchilar/
  O'qituvchilar — `AdminNav.tsx`, now deleted) is its own top-level sidebar
  link instead of a sub-tab bar; a teacher only sees Bosh sahifa/Imtihonlar/
  Sinflar (no Fanlar/O'quvchilar/O'qituvchilar — those stay admin-only).
  `AppHeader` itself is now student-only (+ shared by `ChangePasswordPage`,
  which branches on `user.role` to pick `AppHeader` vs `AdminLayout` since
  that one page is reachable by every role) — don't reintroduce it on a
  teacher/admin page.
  - **`effectiveCollapsed`, not `collapsed`, drives every conditional
    render in the sidebar.** `collapsed` is only the user's stored
    preference; on a narrow viewport (`useIsNarrow()`, a `matchMedia`
    listener, breakpoint 720px) the sidebar is forced icon-only via CSS
    regardless of that preference. The first version of this only had the
    CSS side of that (a `@media` rule hiding `<span>` labels) without
    telling the *components* they were effectively collapsed — so
    `LanguageSwitcher` kept rendering its full "UZ | RU" pill inside a
    64px-wide column and it wrapped/overflowed (a real bug the user
    screenshotted). Fixed by computing `effectiveCollapsed = collapsed ||
    isNarrow` once and threading it through every conditional in
    `AdminLayout.tsx`, including a `compact` prop on `LanguageSwitcher`
    that swaps the two-button pill for a single 32px circular toggle
    (cycles uz→ru→uz) matching `ThemeToggle`'s size. If you add another
    control to the sidebar's bottom tools row, give it a compact variant
    too rather than assuming it'll degrade gracefully in a narrow column.
- **Dashboards** (frontend-only, no new backend endpoints beyond what
  classes/homeroom already needed above — everything is computed
  client-side from data the existing list endpoints already return, since
  the school-scale row counts make that cheap):
  - `frontend/src/features/admin/DashboardPage.tsx` (`/admin/dashboard`,
    teacher+admin) is the landing page after staff login (was
    `/admin/exams`, a bare list — `StaffLoginPage.tsx` points here now).
    Admin sees school-wide stat cards (classes/subjects/students/teachers/
    exams) plus two charts: a donut of exam-status counts
    (`DonutChart.tsx`) and a bar chart of students-per-class
    (`BarChart.tsx`, top 10, admin-only data). Teacher sees their own
    assignment count instead of the school-wide stat cards (`GET
    /admin/teachers/me/assignments`, empty for admin by existing design)
    plus the same status donut scoped to their own exams. Both see "needs
    review" and "active/upcoming" exam lists, scoped automatically because
    `GET /admin/exams` already filters by the teacher's
    `teacher_class_subjects` pairs (`admin_exams.py:list_exams`) — the
    dashboard doesn't re-implement that scoping, it just consumes it.
  - `frontend/src/components/ui/StatCard.tsx` + `.sp-statcard-grid` (in
    `statcard.css`) — reused on the dashboard, `RankingPage.tsx`
    (attempt-status summary strip), and `ClassDetailPage.tsx`.
  - `frontend/src/components/ui/{BarChart,DonutChart,Sparkline}.tsx` — all
    dependency-free inline SVG/CSS charts (no charting library added).
    `Sparkline` is on the student `ProfilePage.tsx` per-subject cards, only
    rendered when a subject has 2+ exam results (a 1-point line is
    meaningless, so it's suppressed). `DonutChart` uses a CSS
    `conic-gradient`, not SVG — simplest way to get a ring chart with zero
    dependencies.
  - `window.confirm()` doesn't fire in the in-app browser pane used for
    manual verification in this environment (silently returns `false`) —
    keep using an in-page two-step confirm pattern (see the class-password
    -reset and homeroom-reassign forms) for any future destructive action's
    UI here rather than native dialogs, both because of that and because
    it matches the design system better anyway.
- **Full CRUD (edit + delete) on every admin-managed entity** — classes,
  subjects, students, teachers all got a `PUT`/`DELETE` pair (classes'
  `PUT` already existed for the homeroom-teacher feature above; this added
  the rest: `PUT`/`DELETE /admin/subjects/{id}`, `DELETE
  /admin/classes/{id}`, `DELETE /admin/students/{id}`, `PUT` (now +
  `full_name`) / `DELETE /admin/teachers/{id}`). The shared rule across
  every delete endpoint in `admin_management.py`: **block with 409 when
  real data depends on the row** (an exam referencing the class/subject, a
  student's exam attempts, a teacher's created exams) rather than letting
  a delete silently orphan grading history — but **silently clean up
  harmless join-table/label references** rather than making the admin do
  that by hand first (deleting a class removes its
  `teacher_class_subjects` rows; deleting a subject clears it from any
  teacher's `subject_id` "asosiy fan" label; deleting a teacher removes
  their `teacher_class_subjects` rows and unsets `homeroom_teacher_id` on
  any class pointing to them). Deleting a student with any `ExamAttempt`
  is blocked — the UI's error message tells the admin to deactivate
  instead, since deactivation was already there and doesn't lose grading
  history. See `app/tests/test_admin_crud.py` for the exact block/allow
  matrix per entity; re-read it before changing what a delete allows.
  Student/teacher class-reassignment authorization is untouched — the
  homeroom rules from the section above still gate who can delete/edit
  which student.
  - `frontend/src/components/ui/ConfirmButton.tsx` — the shared two-click
    delete-confirmation control (label flips to a caller-supplied
    confirm label + `variant="danger"` on first click, fires
    `onConfirm` on the second click within 4s, auto-resets after that).
    Used for every delete action across `SubjectsPage.tsx`,
    `StudentsPage.tsx`, `TeachersPage.tsx`, `ClassDetailPage.tsx` — reuse
    it rather than hand-rolling another two-step pattern (the class
    -password-reset form predates this component and still has its own
    inline version; a future cleanup could switch it over, low priority).
  - Rename ("Tahrirlash") is inline-editable per row on
    `SubjectsPage.tsx`/`StudentsPage.tsx` (a `Card` with input(s) replaces
    the row while editing) and, on `TeachersPage.tsx`, a small form that
    opens below the row without replacing it (that row already toggles an
    assignment-editor panel on click, so replacing the whole row would
    conflict with that). `ClassDetailPage.tsx` (admin only) edits
    grade_level/label/display_name the same way, plus a delete button
    that navigates back to `/classes` on success.
  - The uz translation for "deactivate" used to say "O'chirish" (the same
    word as "delete") on both students and teachers — harmless before
    real delete existed, but confusing once a real delete button sat next
    to it. Changed to "Faolsizlantirish"; don't revert that thinking it's
    a redundant-looking change.
- **Editing a published (scheduled/active) exam is now allowed — right up
  until a student actually starts it.** Originally locked hard at publish
  time; the user asked whether a teacher could still fix a scheduled exam,
  and the agreed rule (confirmed explicitly, two other options — "only
  before the window opens" and "admin-only, always" — were on the table
  and rejected) is: **editable as long as zero `ExamAttempt` rows exist for
  it**, regardless of status. A started attempt snapshots the question/
  option order and eventually a score, so editing after that would desync
  a student's in-progress view or invalidate a recorded grade — that's the
  one hard line, not the draft/review status.
  - `exam_service.ensure_no_attempts(db, exam)` (replaced the old
    `ensure_editable`/`ensure_not_started`, which respectively keyed off
    "status is draft/review" and "now < start_at" — both wrong now) is the
    single check used by `update_exam` and all four question/option CRUD
    endpoints in `admin_exams.py`. `exam_service.has_attempts(db, exam)`
    is the underlying query, also exposed on every `ExamOut` as
    `can_edit: bool` (`_exam_out` in `admin_exams.py`) so the frontend
    doesn't re-derive the rule itself.
  - `recompute_total_points(db, exam)` changed signature (now takes `db`,
    queries `Question.points` directly via `func.sum` instead of reading
    `exam.questions`) and is now called after every add/update/delete
    question — not just at publish — since a published exam's
    `total_points` can change post-publish and `grading_service.py` reads
    it at grading time (`attempt.max_score = exam.total_points`). Forgetting
    this call after a future question-mutation endpoint would silently
    desync a student's max_score from their actual question set.
  - `ExamReviewEditor.tsx`: `locked = !exam.can_edit` (was status-based).
    When locked, all fields/buttons stay disabled and a hint explains why
    ("allaqachon boshlagan o'quvchilar bor"). The publish button only
    renders when `status` is draft/review (`canPublish`); once already
    published it's replaced with a note that editing is still possible
    above as long as nobody's started — publishing again isn't a flow,
    editing-in-place is.
  - Found and fixed a real, previously-uncovered bug while adding test
    coverage here: `Question.options` had no delete cascade, so
    `DELETE /admin/exams/{id}/questions/{id}` 500'd (SQLAlchemy tried to
    null out `QuestionOption.question_id`, a NOT NULL column, instead of
    deleting the rows). Fixed with `cascade="all, delete-orphan"` on
    `Question.options` in `app/models/exam.py`. No test had ever exercised
    that endpoint via HTTP before `test_exam_editing.py`.

- **`parse_confidence` on questions, surfaced to the review UI.** Previously
  the parser's own confidence signal (`ParsedQuestion.confidence`, set in
  `docx_parser.py`/`pdf_parser.py` based on whether an answer key was found
  and exactly 4 options were parsed) was computed but discarded at
  materialization time — only visible in `ExamUpload.raw_parse_debug`
  (diagnostic-only, not shown to anyone). The user confirmed adding a real
  column was worth it: `Question.parse_confidence: str | None` (migration
  `c7e4a2f91b3d_add_parse_confidence_to_questions`, `"high"`/`"low"`/`None`
  — `None` for manually added questions, never set by anything but
  `parsing_service.process_upload`) is now set from `parsed_q.confidence`
  when materializing parsed questions, exposed on `QuestionOut`, and
  rendered as a red "Parser noaniq o'qigan" (low-confidence) badge next to
  the existing "Tekshirilmagan" badge in `ExamReviewEditor.tsx` — so a
  teacher reviewing a parsed exam knows which questions the parser was
  actually unsure about, not just which ones haven't been reviewed yet
  (those are independent signals: a manually-reviewed question can still
  have been a low-confidence parse originally). Don't repurpose this column
  for anything auto-approval-related — see "Parsing approach" below, every
  parsed question still always needs manual review regardless of
  confidence.

- `backend/app/models/` — all SQLAlchemy models for the schema below. Every
  `DateTime(timezone=True)` column uses `UTCDateTime`
  (`app/core/timeutil.py`) instead — see "Timezone handling" below, this is
  load-bearing, don't revert it to plain `DateTime(timezone=True)`.
- `backend/app/routers/` — auth, student, admin_exams, admin_management,
  results all implemented.
- `backend/app/services/` — exam_service (publish validation),
  attempt_service (start/answer/submit, deadline enforcement),
  grading_service, ranking_service, parsing_service all implemented.
- `backend/app/parsers/` — docx_parser/pdf_parser implemented (regex
  block-splitting + "Javoblar:" answer-key detection + bold-run fallback
  for DOCX).
- `backend/app/tasks/` — Celery parsing + exam-lifecycle beat tasks wired.
- `backend/migrations/` — Alembic migrations (structurally verified against
  sqlite; not yet run against a live Postgres instance — the user will do
  this themselves against a DigitalOcean VPS rather than local
  Docker/WSL2, see README.md).
- `frontend/src/` — student + admin/teacher flows implemented and manually
  verified working in-browser (see above), now restyled with a real design
  system (`frontend/src/styles/tokens.css`, `frontend/src/components/ui/`)
  sourced from Spetion's own brand/tokens artifact — brand red `#dd1808`
  used sparingly (primary actions/active states only), Inter for prose,
  Space Mono for numeric "data" (times, scores, countdowns), light+dark
  themes via `prefers-color-scheme`. Logos in `frontend/src/assets/logos/`
  are the brand's own files, copied as-is — never recolor/reconstruct them.
  Reusable pieces: `Button`, `Badge`, `Card`, `ListRow` (4 states: resting/
  now/next/free), `AnswerOption`, `AppHeader`, `Logo`. `formatDate.ts`
  formats Uzbek dates manually — browser ICU uz-UZ month names aren't
  reliable (render as "M09" etc.), don't switch back to
  `toLocaleDateString("uz-UZ", ...)`.

### Timezone handling — read before touching datetime columns

Postgres `TIMESTAMPTZ` always round-trips timezone-aware in Python via
psycopg2. **sqlite does not** — it silently drops the UTC offset on
read-back. This bit twice in the same live-testing session: (1) a naive
value compared against `datetime.now(timezone.utc)` raises `TypeError`,
and (2) a naive value serialized to JSON has no `Z`/offset suffix, which
browsers parse as *local* time — this actually corrupted the exam
countdown timer (a deadline meant as UTC got read as local time, so the
timer showed the exam as already expired and auto-submitted it instantly).
Fixed at the source: every datetime column model-wide uses `UTCDateTime`
(a `TypeDecorator` in `app/core/timeutil.py` that reattaches UTC tzinfo on
read if missing), so values are guaranteed aware regardless of backend.
`app.core.timeutil.aware()` is also available as a defense-in-depth guard
at comparison call sites (used in `attempt_service.py`, `exam_service.py`,
`routers/student.py`). Since local dev without Docker (sqlite) is a real,
now-proven usage pattern for this project, keep using `UTCDateTime` for
any new datetime column rather than raw `DateTime(timezone=True)`.

Known gaps (see README.md "Hali qilinmagan" for the full list): no live-DB
migration run yet (the user will run it against a DigitalOcean VPS
Postgres instance rather than local Docker/WSL2 — give them the
`alembic upgrade head` command and a `DATABASE_URL` pointed at that VPS
when they're ready, no code changes needed), no short-answer manual
grading (explicitly deferred by the user — not needed yet since grading
free-text answers costs a teacher's time either way; the user floated
having an AI model grade short-answers automatically as a *future* idea,
not committed to, so raise it again rather than assuming it's still
wanted if this comes back up), and the real-world-scanned-PDF /
complex-math-test parsing accuracy question is still open (the user is
looking for real sample files to try). `parse_confidence` is no longer a
gap — see the bullet under "Current status" above.

## Database schema (target — see the full write-up in `docs/spec.md`)

Key tables: `users`, `classes` (sinf), `subjects`, `students`, `teachers`,
`teacher_class_subjects`, `exam_uploads`, `exams`, `questions`,
`question_options`, `exam_attempts`, `student_answers`, `exam_rankings`,
`student_subject_stats`. Full column-level detail is in `docs/spec.md`.

Rules that must not be violated by any future code:
- `exam_attempts` has a UNIQUE `(exam_id, student_id)` — one attempt per
  student per exam, enforced at the DB level (not just app logic), to avoid
  race conditions when a whole class starts at once.
- A `questions` row parsed from a file is **always** created with
  `needs_review=true`. An exam can never reach `status='scheduled'`
  (published) while any of its questions still has `needs_review=true`.
  This check happens in the `/admin/exams/{id}/publish` endpoint itself —
  never rely on the frontend to enforce it.
- The exam timer is never trusted from the client. The server issues an
  absolute `deadline_at` timestamp when a student starts. Every write
  endpoint (`/answers`, `/submit`) independently rejects writes made after
  `deadline_at`. A Celery beat task is the actual authority that force-
  submits attempts whose deadline passed — the client countdown is UX only.

## Exam lifecycle

upload → Celery parses PDF/DOCX → draft questions created (`needs_review=
true`) → teacher reviews/edits/approves each → teacher sets `duration_minutes`
+ `start_at`/`end_at` → publish (validates: all questions reviewed, each MCQ
has exactly 4 options with exactly 1 correct) → students take it inside the
window with a server-issued deadline → auto-grade on submit → per-class
ranking recomputed → `student_subject_stats` updated incrementally.

## Parsing approach

- DOCX via `python-docx`, PDF via `pdfplumber` (OCR fallback via
  `pytesseract` for scanned PDFs, flagged low-confidence).
- Regex/heuristic question-block splitting (numbering patterns), not
  ML/LLM, for v1. Answer-key detection tries, in order: inline "Javoblar:"
  text, an answer-key **table** (a real format a teacher's file used: a
  "Savol"/"Javob" row pair — `python-docx` only reads paragraph text by
  default, so `docx_parser.py` has a dedicated `_extract_table_answer_key`
  pass over `document.tables`), then bold-run fallback. If a new real-world
  file uses yet another answer-key layout, add another extractor rather
  than assuming the existing ones cover it — this has already happened
  once.
- Every parsed question always needs manual review — do not add
  auto-approval logic without discussing it first, grading integrity
  depends on this.

## Next steps (in order)

1. User will stand up real Postgres on a DigitalOcean VPS (not local
   Docker/WSL2 — that path is superseded) and run `alembic upgrade head`
   against it themselves; just be ready to help with `DATABASE_URL`/
   connection-string questions when they do.
2. PDF parsing is now covered by real tests (`app/tests/test_parsers.py`,
   `reportlab`-generated synthetic PDFs — a normal text PDF with a trailing
   "Javoblar:" key, one with no key at all so options parse but nothing is
   marked correct/`confidence="low"`, and a blank/no-text-layer page to
   prove the OCR fallback never crashes) and was also manually driven
   through the full upload → S3(local) → Celery(eager) → materialize
   pipeline. It has **not** been tried against a real scanned/photographed
   exam PDF, or a complex math exam (formulas, fractions, roots — unclear
   how these come through as text vs. images), from a teacher yet — the
   user is actively looking for real sample files to test with; when they
   arrive, run them through the same upload pipeline and check both parse
   accuracy and whether `patterns.py`'s question-splitting regex still
   holds up against math notation.
3. Short-answer manual grading — deferred by the user for now, not
   current work (see "Known gaps" above for the AI-grading idea floated
   for later).

## Running locally

```
docker-compose up -d        # postgres, redis, minio
cd backend && uvicorn app.main:app --reload
cd frontend && npm run dev
```

See `README.md` for first-time setup.

### Known environment issue: `uvicorn --reload` on Windows

In this dev setup, `uvicorn --reload` (WatchFiles) has repeatedly stopped
picking up file changes after the first reload in a multi-file edit
session — symptoms are 404s on routes that were just added, or 422s citing
fields that were just removed from a schema, even though the source on
disk is correct. If backend behavior doesn't match the code you just
edited, don't assume a code bug first: kill the process (`taskkill //F
//PID <pid>`) and restart plain `uvicorn app.main:app --port 8000`
*without* `--reload`, then retest. This means manual restarts after every
backend edit are currently the reliable path on Windows.
