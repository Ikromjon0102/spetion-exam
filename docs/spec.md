# Spetion Exam Platform — Full Technical Spec

(Full detail behind the summary in `CLAUDE.md`. Written up during planning
before any code existed — treat as the design source of truth; update it if
implementation reveals a better approach, don't silently drift from it.)

## 0. Stack decision

**Backend: FastAPI**, over Django/Flask. Async I/O matters for file
upload/parsing and timed auto-submission; Pydantic gives strict validation
for the nested question/option schema; a custom React admin UI means
Django's templating/admin convenience isn't used anyway; Flask lacks
built-in async/validation/OpenAPI.

**DB: PostgreSQL.** JSONB used sparingly (raw-parse debug blobs only),
otherwise fully normalized relational schema.

**Redis** — exam session/timer bookkeeping, Celery broker, login rate
limiting, leaderboard cache.

**Celery + Redis** — background worker for PDF/DOCX parsing and the
scheduled auto-submit sweep / grading trigger.

**S3-compatible storage** (MinIO locally) — raw uploaded exam files.

## 1. Database schema

All tables: `id BIGSERIAL PRIMARY KEY` unless noted, `created_at`/
`updated_at TIMESTAMPTZ DEFAULT now()`. FKs `ON DELETE RESTRICT` unless
stated.

### 1.1 Identity & org structure

**schools** — `id`, `name`, `address`, `is_active` (future multi-school
proofing; v1 is single-tenant).

**academic_years** — `id`, `school_id FK`, `label`, `start_date`,
`end_date`, `is_current BOOLEAN`.

**classes** (sinf) — `id`, `school_id FK`, `academic_year_id FK`,
`grade_level INT`, `label VARCHAR`, `display_name VARCHAR`. UNIQUE
`(academic_year_id, grade_level, label)`.

**users** — `id`, `username VARCHAR UNIQUE NOT NULL`,
`password_hash VARCHAR NOT NULL`, `role ENUM('student','teacher','admin')`,
`full_name`, `phone VARCHAR NULL`, `is_active BOOLEAN DEFAULT true`,
`last_login_at`. One table for auth identity across all roles keeps login
simple (one endpoint, one JWT `sub`); role-specific data lives in child
tables.

**students** — `id`, `user_id FK UNIQUE`, `class_id FK -> classes`,
`student_code VARCHAR UNIQUE`, `enrolled_at DATE`.

**teachers** — `id`, `user_id FK UNIQUE`, `subject_id FK NULL`.

**teacher_class_subjects** — `id`, `teacher_id FK`, `class_id FK`,
`subject_id FK`. UNIQUE `(teacher_id, class_id, subject_id)`. Used to
authorize "can this teacher create/edit this exam."

**subjects** — `id`, `name VARCHAR UNIQUE`, `code VARCHAR`.

### 1.2 Exam authoring pipeline

**exam_uploads** — `id`, `uploaded_by_id FK -> users`,
`original_filename`, `file_type ENUM('pdf','docx')`, `storage_key`,
`status ENUM('pending','parsing','parsed','parse_failed')`,
`parse_error TEXT NULL`, `raw_parse_debug JSONB NULL` (diagnostic only,
never read again by app logic once questions are materialized).

**exams** — `id`, `title`, `subject_id FK`, `class_id FK`,
`created_by_id FK -> users`, `exam_upload_id FK NULL`,
`status ENUM('draft','review','scheduled','active','closed','archived')`,
`start_at TIMESTAMPTZ`, `end_at TIMESTAMPTZ`,
`duration_minutes INT NOT NULL` (per-student time budget, distinct from the
window), `total_points NUMERIC`, `shuffle_questions BOOLEAN DEFAULT true`,
`shuffle_options BOOLEAN DEFAULT true`, `published_at TIMESTAMPTZ NULL`.

Multi-class exams: keep `exams` 1-class for v1 (leaderboard logic stays
simple). If needed later, add a nullable `exam_group_id UUID` shared across
rows purely for UI grouping — don't model as many-to-many.

**questions** — `id`, `exam_id FK`, `order_index INT`,
`question_type ENUM('mcq','short_answer')`, `prompt_text TEXT`,
`prompt_image_key VARCHAR NULL`, `points NUMERIC DEFAULT 1`,
`source ENUM('parsed','manual')`, `needs_review BOOLEAN DEFAULT true`.

**question_options** — `id`, `question_id FK`, `order_index INT`,
`option_text TEXT`, `is_correct BOOLEAN DEFAULT false`. Exactly-4/exactly-
1-correct is an app-layer invariant (service layer + publish-time
validator), not a DB constraint.

### 1.3 Taking exams

**exam_attempts** — `id`, `exam_id FK`, `student_id FK`, UNIQUE
`(exam_id, student_id)`,
`status ENUM('not_started','in_progress','submitted','auto_submitted','expired_unstarted')`,
`started_at TIMESTAMPTZ NULL` (timer basis, not `exams.start_at`),
`deadline_at TIMESTAMPTZ NULL` (= `started_at + duration_minutes`, capped
at `exams.end_at`), `submitted_at TIMESTAMPTZ NULL`, `score NUMERIC NULL`,
`max_score NUMERIC NULL`, `question_order JSONB` (shuffled order persisted
at start so refresh/review show the same order).

**student_answers** — `id`, `attempt_id FK`, `question_id FK`,
`selected_option_id FK NULL`, `answer_text TEXT NULL`,
`is_correct BOOLEAN NULL`, `points_awarded NUMERIC NULL`,
`answered_at TIMESTAMPTZ`. UNIQUE `(attempt_id, question_id)` — upsert per
answer (autosave).

### 1.4 Results / performance history

**exam_rankings** — `id`, `exam_id FK`, `student_id FK`,
`class_id FK` (denormalized), `score NUMERIC`, `rank_in_class INT`,
`percentile NUMERIC NULL`. UNIQUE `(exam_id, student_id)`. Index
`(exam_id, rank_in_class)`.

**student_subject_stats** — `id`, `student_id FK`, `subject_id FK`,
`exams_taken_count INT`, `total_points_earned NUMERIC`,
`total_points_possible NUMERIC`, `average_percent NUMERIC`,
`last_exam_at TIMESTAMPTZ`, `trend ENUM('improving','declining','stable')
NULL`. UNIQUE `(student_id, subject_id)`. This is what the student-profile
"progress over time" view reads directly; per-exam drill-down comes from
`exam_attempts JOIN exams`.

## 2. API endpoints (`/api/v1`, JWT auth, role-checked via DI)

**Auth**: `GET /auth/classes`, `POST /auth/login`, `POST /auth/refresh`,
`POST /auth/logout`, `GET /auth/me`.

**Student**: `GET /student/me/profile`,
`GET /student/me/subjects/{id}/history`, `GET /student/me/exams`,
`GET /student/exams/{id}`, `POST /student/exams/{id}/start`,
`GET /student/exams/{id}/attempt`,
`PUT /student/exams/{id}/answers/{q_id}`,
`POST /student/exams/{id}/submit`, `GET /student/exams/{id}/result`,
`GET /student/exams/{id}/ranking`.

**Admin — org management**: `GET/POST /admin/classes`,
`GET/POST /admin/subjects`, `GET/POST /admin/students`,
`POST /admin/students/bulk-import`, `GET/POST /admin/teachers`.

**Admin — exam authoring**: `POST /admin/exams/uploads`,
`GET /admin/exams/uploads/{id}`, `POST /admin/exams`,
`GET /admin/exams`, `GET /admin/exams/{id}`, `PUT /admin/exams/{id}`,
`PUT /admin/exams/{id}/questions/{q_id}`,
`PUT /admin/exams/{id}/questions/{q_id}/options/{opt_id}`,
`POST /admin/exams/{id}/questions`,
`DELETE /admin/exams/{id}/questions/{q_id}`,
`POST /admin/exams/{id}/publish`, `POST /admin/exams/{id}/close`.

**Admin — results**: `GET /admin/exams/{id}/ranking`,
`GET /admin/exams/{id}/attempts`,
`GET /admin/exams/{id}/attempts/{student_id}`,
`GET /admin/classes/{id}/subjects/{id}/performance`,
`GET /admin/students/{id}/performance`.

## 3. Exam lifecycle, step by step

1. **Upload** — teacher POSTs file → streamed to S3/MinIO,
   `exam_uploads` row `status=pending`, Celery task enqueued, 202 returned
   immediately (never block on parsing).
2. **Parse (worker)** — downloads file, extracts text, produces
   `{prompt, options[4], correct_index}` guesses, writes
   `raw_parse_debug`, sets `status=parsed`/`parse_failed`. Materializes
   `exams` (`status='draft'`) + `questions`/`question_options`
   (`needs_review=true`, `source='parsed'`) in the same task.
3. **Teacher review** — question-by-question editor; fix text, correct the
   marked answer, delete garbage, add missed questions manually; clears
   `needs_review` per question. Exam stays invisible to students
   (`draft`/`review`).
4. **Schedule + publish** — set `duration_minutes`, `start_at`, `end_at`,
   call `/publish`. Validation (all must pass): every MCQ has exactly 4
   options/1 correct; no `needs_review=true` remains; `start_at < end_at`;
   `duration_minutes <= (end_at - start_at)`; ≥1 question. On success:
   `status='scheduled'`, `published_at=now()`, `total_points` recomputed.
   **After publish, question/option edits are rejected (409)** — add an
   explicit `/unpublish` (only while `now() < start_at`) if a fix is truly
   needed.
5. **Window open** — `status` transitions are computed lazily at read time
   (`start_at <= now() < end_at`); a beat task also updates the stored
   column for query convenience, but the authoritative check is always a
   live timestamp comparison inside `/start`.
6. **Student starts** — reject if outside window or attempt already
   exists; else create `exam_attempts`, `started_at=now()`,
   `deadline_at = min(now() + duration_minutes, end_at)`; shuffle
   questions/options with a seeded RNG (seed = `attempt.id`) so it's
   reproducible without storing full shuffled objects; return questions
   (no `is_correct`) + `deadline_at`.
7. **Timer / auto-submit** — client counts down from server-issued
   `deadline_at` (absolute timestamp, re-synced on tab focus, never a
   client-computed duration); on 0 it calls `/submit`. Independently, a
   Celery beat task every ~15-30s force-submits any
   `in_progress` attempt whose `deadline_at` has passed — this, not the
   client, is what guarantees the cutoff. `/submit` and
   `PUT /answers/{q_id}` themselves reject writes with
   `now() > deadline_at`.
8. **Grading** — runs synchronously in `/submit` (MCQ grading is cheap:
   join `selected_option_id` against `is_correct`, sum points). The beat
   auto-submit path calls the exact same grading service function so
   behavior is identical either way.
9. **Ranking** — recomputed after each individual submit (not batched):
   update that student's `exam_rankings` row, recompute `rank_in_class` for
   the class via a `RANK() OVER (PARTITION BY exam_id ORDER BY score DESC)`
   query, upsert `student_subject_stats` incrementally.
10. **Post-window** — beat task marks still-`not_started` attempts
    `expired_unstarted` once `end_at` passes (excluded from
    `exam_rankings`, visible in the admin attempts list as "did not
    take").

## 4. PDF/DOCX parsing

**Libraries**: `python-docx` for DOCX; `pdfplumber` for PDF (better
text-flow reconstruction than PyPDF2/pypdf); `pytesseract` OCR fallback
for scanned PDFs with no text layer (flag OCR output lower-confidence,
don't over-invest in OCR quality for v1 — just don't crash, and always
route to manual review).

**Strategy — regex/heuristic, not ML/LLM, for v1**:
1. Extract plain text preserving line breaks.
2. Split into question blocks via a small ordered list of numbering
   patterns (`PARSER_QUESTION_PATTERNS` config constant, tunable without
   touching parsing logic elsewhere) — e.g. `^\d+[\.\)]\s`, `\d+-savol`.
3. Within each block, extract 4 options via `^[A-D][\.\)]\s` /
   `^[a-d][\.\)]\s` patterns.
4. Detect the correct option: bold runs (DOCX `run.bold`; unreliable in
   PDF), asterisk/star prefix, underline, or — most reliable — a trailing
   "Javoblar: 1-B, 2-A..." answer-key section, cross-referenced by question
   number when present.
5. Every parsed question gets `needs_review=true` unconditionally in v1 —
   no auto-clearing on high confidence, grading integrity depends on
   always reviewing. (Possible v1.1: only auto-clear when an answer-key
   cross-reference confirmed the option AND exactly 4 options were found
   cleanly — don't build this until v1 ships.)
6. Anything that fails to parse cleanly still becomes a `questions` row
   with best-effort content and a `parse_confidence ENUM('high','low')`
   flag surfaced prominently in the review UI.

**Where it runs**: Celery worker (`tasks/parsing.py`) — never inline in
the request.

**Short-answer**: schema already supports it (`question_type`,
`answer_text`). Auto-grading free text reliably is not easy — ship v1.1
as teacher-manual-grading (a dedicated grade endpoint setting
`points_awarded`, `exam_attempts.score` recomputed as a sum after manual
grading closes) rather than fuzzy NLP matching.

## 5. Folder structure

See `backend/` and `frontend/` in this repo — the scaffold already follows
this layout; keep new files in the matching place.

```
backend/app/
  main.py            core/            db/
  config.py            security.py      base.py
  dependencies.py       exceptions.py    migrations/ (alembic)
  models/            services/         parsers/
  schemas/           routers/          tasks/
  tests/

frontend/src/
  api/   auth/   features/student/   features/admin/
  features/shared/   components/   hooks/   routes/   store/   types/
```

## 6. Trickiest risks

1. **Timer integrity** — client clock/network cannot be trusted. Solved by
   server-issued absolute `deadline_at`, every write endpoint rejecting
   late writes independently, and the beat-task sweep as the real
   authority — client countdown is UX only, correctness never depends on
   it firing.
2. **Parsing accuracy** — inconsistent PDF layouts, scanned images,
   answer-key sometimes absent; a silent bad parse corrupts every
   student's grade. Solved by making manual review structurally mandatory
   (`/publish` enforces `needs_review=false` server-side, never just in
   the UI) and surfacing `parse_confidence` to direct attention.
3. **Concurrency at start/grading** — a whole class hitting `/start` at
   the same second, or many submits near the deadline sweep. Solved by the
   DB-level UNIQUE `(exam_id, student_id)` constraint with
   `INSERT ... ON CONFLICT DO NOTHING` (never app-level check-then-insert),
   and a row-level lock on the `exam_attempts` row during grading so the
   beat sweep and a late manual `/submit` can't double-grade the same
   attempt.
