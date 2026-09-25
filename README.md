# AI Resume-Based Theory Interview Assistant

Stack: React + Tailwind (Vite) · Django REST Framework · FastAPI (AI service) · PostgreSQL · JWT (SimpleJWT) · PyMuPDF · Gemini API (google-genai) · ChromaDB · Pydantic-structured Gemini outputs · Docker · n8n

## Module 1 — Authentication & User Management

- Signup (Name, Email, Password, Confirm Password) with server-side validation
- Login / Logout using JWT access + refresh tokens (logout blacklists the refresh token)
- Multi-user accounts, email enforced unique at the database level
- Profile screen: Name + Email only (nothing else is stored or shown)
- Change Password (requires current password, hashed with Django's PBKDF2 by default)
- Every non-auth endpoint requires a valid JWT; profile/password endpoints always
  operate on `request.user` — there is no by-ID lookup, so one user can never
  read or edit another user's data
- Dark-mode, mobile-responsive UI

Not included (per spec): Forgot Password, Email Verification, mobile app, profile photo, settings page.

## Module 2 — Resume Upload & Processing

- Logged-in user can upload exactly **one** PDF resume (`resumes` app, `Resume` model
  is a `OneToOneField` to the user — a second upload is rejected with `409 Conflict`,
  not overwritten; no replace or delete flow exists, per spec)
- Upload validation, in order: file present and non-empty → size ≤ `MAX_RESUME_SIZE_MB`
  (default 5MB) → filename ends in `.pdf` → `content_type` is `application/pdf` →
  actual file bytes start with the real PDF signature (`%PDF-`), so a renamed
  `.txt` file or a spoofed `content_type` header is still caught
- File is stored under `media/resumes/user_<id>/<random-uuid>.pdf` — never the
  original filename on disk, so one user can't guess or collide with another's path
- Text is extracted synchronously at upload time with PyMuPDF (`resumes/services.py`);
  if extraction fails (corrupt/encrypted/scanned-image PDF with no text layer),
  the upload is rolled back — no file or DB row is left behind — and a clear
  error is returned
- `GET /api/resumes/me/` always resolves to `request.user`'s own resume only —
  there is no by-ID resume endpoint, so isolation holds structurally, not just
  by permission check
- Home page: shows a loading state while checking status, an upload form with
  client-side validation + progress bar + inline errors when no resume exists
  yet, and a simple read-only "uploaded & processed" card once one does

### New/changed files in Module 2

- New: `backend/resumes/` (models, services, serializers, views, urls, admin, tests, migration)
- Changed (additive only): `backend/config/settings.py` (added `resumes` app + media/upload
  settings), `backend/config/urls.py` (added `/api/resumes/` route + media serving in DEBUG)
- New: `frontend/src/pages/Home.jsx`, `frontend/src/api/resumeApi.js`
- Changed (additive only): `frontend/src/api/axios.js` (factored the existing interceptor
  logic into a reusable client builder so `resumeApi.js` can share the same
  token-attach/refresh behavior — the exported `api` default and `BASE_URL` are
  unchanged, so nothing that already used them needed to change),
  `frontend/src/App.jsx` (added `/home` route, now the post-login landing page),
  `frontend/src/pages/Login.jsx` (redirects to `/home` instead of `/dashboard`
  after login), `frontend/src/components/Navbar.jsx` (added a Home link)

Module 1's signup/login/logout/profile/change-password code was not modified
beyond the above navigation wiring.

## Module 3 — Resume Analysis & ATS

- New `analysis` app calls the Gemini API (`google-genai` SDK) to analyze
  `request.user`'s own processed resume text and stores the structured result
- `ResumeAnalysis` is a `OneToOneField` to `Resume` — one analysis per resume,
  matching the one-resume-per-user design from Module 2
- Gemini is constrained to a Pydantic `response_schema` (`analysis/services.py`),
  so the model returns exactly: `ats_score` (0-100), `strengths`, `weaknesses`,
  `extracted_skills`, `projects_experience`, `suggested_roles` (each with its
  own `required_skills` and `missing_skills`), and `improvement_suggestions` —
  no manual JSON parsing or hoping the model follows a text prompt
- `POST /api/analysis/analyze/` and `GET /api/analysis/me/` both resolve only
  through `request.user`'s own resume (`Resume.objects.filter(user=user)`) —
  there is no endpoint that accepts a resume ID or user ID, so analyzing or
  reading another user's resume is not possible by construction
- `analyze/` is idempotent once completed: a second call returns the stored
  result instead of re-spending a Gemini call; a prior failure is retried
- On a Gemini failure (bad/missing API key, network error, malformed
  response), the analysis is recorded with `status: "failed"` and the
  endpoint returns `502` with a plain-language error — nothing crashes and
  the resume itself is untouched
- Home page: once a resume shows as processed, it automatically checks for
  an existing analysis and triggers one if needed (no extra button) — shows
  an "Analyzing your resume…" loading state, a clear error + **Retry
  analysis** button on failure, and the results in simple cards (ATS score,
  strengths, weaknesses, skills, projects/experience, suggested roles with
  their required/missing skills, and improvement suggestions) once done

### New/changed files in Module 3

- New: `backend/analysis/` (models, services, serializers, views, urls,
  admin, tests, migration)
- Changed (additive only): `backend/config/settings.py` (added `analysis`
  app + `GEMINI_API_KEY`/`GEMINI_MODEL`), `backend/config/urls.py` (added
  `/api/analysis/` route), `backend/requirements.txt` (added `google-genai`)
- New: `frontend/src/api/analysisApi.js`, `frontend/src/components/AnalysisSection.jsx`
- Changed (additive only): `frontend/src/api/axios.js` (added one more
  `createAuthedClient(...)` call for the analysis endpoints — the existing
  `api`/`resumesApi` exports are untouched), `frontend/src/pages/Home.jsx`
  (added analysis state, an effect that runs after the resume is confirmed
  processed, and passes results down to the new `ProcessedState` UI)

Modules 1 and 2's code was not modified beyond the additive wiring described above.

## Module 4 — RAG System (resume search for future AI modules)

- New `rag` app implements: resume text → chunk → embed (Gemini) → store
  (ChromaDB) → retrieve, scoped strictly to one user's own resume
- **Chunking** (`rag/services.py::chunk_text`): simple word-count sliding
  window (200 words per chunk, 40-word overlap), no extra text-splitting
  library needed at resume length
- **Embeddings**: Gemini's `gemini-embedding-001` model via the same
  `google-genai` SDK/API key Module 3 already uses — `RETRIEVAL_DOCUMENT`
  task type when indexing chunks, `RETRIEVAL_QUERY` when embedding a search
  query, which measurably improves retrieval quality over using one task
  type for both sides
- **Storage**: a single ChromaDB collection (`resume_chunks`, local
  `PersistentClient`), with every chunk's metadata carrying `user_id` and
  `resume_id`. Isolation is enforced **twice**: once via Chroma's `where`
  filter at query time, and again by checking every returned chunk's
  metadata in Python — a mismatch there raises instead of silently
  filtering, since that would only mean a bug we'd rather fail loudly on
- **No duplicate indexing**: `ResumeIndex` (one row per resume) stores a
  SHA-256 hash of the exact text that was indexed; `index_resume()` is a
  no-op if that hash is already marked `indexed`. Chroma writes also use
  `upsert()` with deterministic IDs (`resume-<id>-chunk-<i>`), so even a
  forced re-run overwrites the same vectors instead of duplicating them
- **Automatic indexing**: a `post_save` signal on `Resume` (registered in
  `rag/apps.py`, not by editing Module 2's code) triggers indexing the
  moment a resume's status becomes `processed`. For resumes that already
  existed before this module was added, `retrieve_relevant_chunks()` indexes
  lazily on first use, and `python manage.py backfill_rag_index` is
  available to index all of them up front instead of waiting
- **Integration point for future modules** (Resume Expert, AI Interviewer,
  Career Coach, AI Tutor): a single function,
  `rag.services.retrieve_relevant_chunks(user, query, top_k=5)`, returns the
  most relevant resume-text chunks for `user`'s own resume, or `[]` if they
  have none. That's the entire interface those modules need — they're all
  part of the same Django backend, so a direct function call is simpler and
  faster than an internal HTTP round-trip
- No frontend or API endpoint was added for this module, per spec — it's a
  backend capability other modules call directly, not something the user
  interacts with themselves yet

### Design note: why no new endpoint

Everything else in this project so far has had a corresponding API endpoint
because a person needed to trigger it directly. RAG doesn't — it exists so
*other backend code* (not yet built) can pull resume context into its own
prompts. Adding an endpoint now would be surface area with no current
caller, which is exactly the kind of extra feature the brief asked to avoid.
If a later module ends up needing RAG over an HTTP boundary (e.g. a separate
service), wrapping `retrieve_relevant_chunks` in a thin authenticated view at
that point is a small, contained change.

### New/changed files in Module 4

- New: `backend/rag/` (models, services, signals, admin, tests, migration,
  and `management/commands/backfill_rag_index.py`)
- Changed (additive only): `backend/config/settings.py` (added `rag` app +
  `GEMINI_EMBEDDING_MODEL`/`GEMINI_EMBEDDING_DIMENSIONS`/`CHROMA_PERSIST_DIR`/
  `CHROMA_COLLECTION_NAME`), `backend/requirements.txt` (added `chromadb`)

No existing file from Modules 1-3 was edited beyond those settings/requirements
additions — the signal-based hook means Module 2's upload view (and every
other existing view) is completely untouched.

## Module 5 — AI Assistant (Resume Expert, AI Interviewer, Career Coach, AI Tutor)

- **One reusable service, four modes**: `assistant/services.py` defines a
  single `AIAssistantService` class (imported as the `ai_assistant`
  singleton). Every mode funnels through the same two primitives — `_chat`
  for free-form conversational replies, `_structured` for JSON-schema-
  constrained output — and the same Gemini client construction. There is
  exactly one place in the codebase that calls `genai.Client(...)`.
- **Shared grounding**: `_resume_context()` combines Module 3's *stored
  analysis* (ATS score, strengths, weaknesses, skills, skill gaps — none of
  which live in the raw resume text, so Module 4's RAG alone can't answer
  "what's my ATS score?") with Module 4's RAG-retrieved raw resume excerpts
  relevant to the current question. Every mode that touches the resume uses
  this same helper, so "never invent resume information" is enforced by one
  grounding rule (`_GROUNDING_RULE`) baked into each relevant system prompt,
  not reimplemented per mode.
- **1. Resume Expert** (`resume_expert_reply`): free-form chat grounded in
  the resume context above — answers questions about ATS compatibility,
  skills, projects, strengths, weaknesses, and skill gaps.
- **2. AI Interviewer**: a structured flow, not free chat —
  `generate_interview_questions()` produces 10-15 theory-only questions
  (a Pydantic `Field(min_length=10, max_length=15)` constraint enforces the
  count; the prompt explicitly forbids coding/code-execution questions),
  personalized using the resume context for the selected role.
  `evaluate_interview_answer()` scores each answer (0-10) with concise
  feedback and an ideal answer, one question at a time.
  `generate_interview_report()` produces the final report (overall score
  0-100, strengths, weak areas, narrative feedback) once all questions are
  answered.
- **3. Career Coach** (`career_coach_reply`): free-form chat like Resume
  Expert, but also takes an optional target role (stored on the chat
  session) and tailors guidance toward closing the gap between the resume
  and that role.
- **4. AI Tutor** (`tutor_reply`): free-form chat, deliberately *not*
  resume-grounded — explains concepts and evaluates practice answers on
  their own terms, matching the spec's literal scope for this mode.
- **Conversation context**: `ChatSession` is one row per `(user, mode)` —
  a single ongoing thread per mode, not a list of named chats — enforced by
  a DB unique constraint. Each message is stored in `ChatMessage`; the last
  `MAX_HISTORY_MESSAGES` (20) are replayed to Gemini as multi-turn `contents`
  so follow-ups are natural, without resending an ever-growing transcript.
- **Interview state**: `InterviewSession` stores the generated questions,
  progress, the full question-by-question `qa_log`, and the `final_report`.
  Only one `in_progress` interview per user is allowed — enforced by a
  **partial unique DB constraint** (`condition=Q(status="in_progress")`),
  not just an application-level check, so this can't be raced around.
- **Isolation**: every chat and interview endpoint resolves only through
  `request.user` — no session ID, message ID, or interview ID is ever
  accepted from the client. `ChatView` is one class shared by all three chat
  modes (`mode` fixed per URL via `as_view(mode=...)`), so there's a single
  code path to audit rather than three near-duplicate views.
- **Frontend**: a new `/assistant` page with four tabs. Resume Expert,
  Career Coach, and Tutor share one `ChatPanel` component (message list +
  input, with an optional role selector for Career Coach); the Interviewer
  has its own `InterviewPanel` (role selection → one question at a time →
  final report + full Q&A review). Suggested roles for the Career Coach and
  Interviewer role selectors come from Module 3's existing
  `GET /api/analysis/me/` — no new endpoint was needed for that.

### New/changed files in Module 5

- New: `backend/assistant/` (models, services, serializers, views, urls,
  admin, tests, migration)
- Changed (additive only): `backend/config/settings.py` (added `assistant`
  app — no new settings needed, it reuses `GEMINI_API_KEY`/`GEMINI_MODEL`
  from Module 3), `backend/config/urls.py` (added `/api/assistant/` route)
- New: `frontend/src/pages/Assistant.jsx`, `frontend/src/api/assistantApi.js`,
  `frontend/src/components/assistant/ChatPanel.jsx`,
  `frontend/src/components/assistant/InterviewPanel.jsx`
- Changed (additive only): `frontend/src/api/axios.js` (one more
  `createAuthedClient(...)` line, same pattern as Modules 2-4),
  `frontend/src/App.jsx` (added `/assistant` route),
  `frontend/src/components/Navbar.jsx` (added an Assistant link)

No existing file from Modules 1-4 was edited beyond those additions.

## Module 6 — Interview History

- **No duplicate interview records.** History is not a new copy of interview
  data — it's a new `history` app that reads, renames, and deletes Module 5's
  existing `InterviewSession` rows directly. The only schema change is one
  additive field: `InterviewSession.title` (blank by default, added in
  `assistant/migrations/0002_interviewsession_title.py`). Everything else —
  questions, qa_log, final_report — was already there from Module 5.
- **History = completed interviews only.** An in-progress interview isn't
  history yet; it's still reachable via Module 5's own
  `/api/assistant/interview/status/`. Every query in `history/views.py`
  filters on `status=completed`, so a half-finished interview never shows up
  in the list.
- **List**: title (falls back to `role` if never renamed), role, date
  (completion date — see below), overall score, status, question count.
- **Detail**: full questions, the complete `qa_log` (answer, score, feedback,
  ideal answer per question), and the final report — all read straight off
  the same `InterviewSession` row Module 5 already populated.
- **Rename** (`PATCH /api/history/interviews/<id>/`) deliberately uses
  `QuerySet.update()` instead of `save()`. Django's `auto_now` on
  `updated_at` only fires on `.save()`, not on bulk `.update()` — so renaming
  an interview never shifts the "date" shown in history away from when it
  was actually completed. This is a one-line consequence of how the write is
  done, not a separate `completed_at` field or extra bookkeeping.
- **Delete** (`DELETE /api/history/interviews/<id>/`) removes the one
  `InterviewSession` row. Since questions/qa_log/final_report all live as
  JSON on that same row (no related child tables), deleting it *is* deleting
  "all related interview data" — there's nothing else that could be left
  orphaned.
- **Isolation**: every list/detail/rename/delete query filters by
  `user=request.user` **and** `status=completed` together, in one queryset
  (`history/views.py::_own_completed_qs`). An interview that exists but
  belongs to someone else, or exists but isn't completed, is indistinguishable
  from one that doesn't exist at all — always `404`, never a `403` that would
  confirm something exists that the requester can't see.
- **Frontend**: a new `/history` page — a list view (click a card to open
  it) and a detail view (question-by-question review, final report, inline
  rename, and a two-step delete confirmation) in the same component, no
  extra routing needed for something this simple.

### New/changed files in Module 6

- New: `backend/history/` (serializers, views, urls, tests — no `models.py`,
  since this app doesn't own any data of its own)
- Changed (additive only): `backend/assistant/models.py` (added the
  `title` field to `InterviewSession`) with its own migration
  `backend/assistant/migrations/0002_interviewsession_title.py`;
  `backend/assistant/views.py` (`_serialize_interview` now also includes
  `title` — the two exact-dict assertions in Module 5's own tests are both
  for the "no interview" case, so they're unaffected); `backend/config/settings.py`
  (added `history` app); `backend/config/urls.py` (added `/api/history/` route)
- New: `frontend/src/pages/History.jsx`, `frontend/src/api/historyApi.js`
- Changed (additive only): `frontend/src/api/axios.js` (one more
  `createAuthedClient(...)` line), `frontend/src/App.jsx` (added `/history`
  route), `frontend/src/components/Navbar.jsx` (added a History link)

This is the one module so far that touches a Module 5 file for a reason
beyond settings/urls wiring — adding `title` to `InterviewSession` was
unavoidable given "use existing interview data, don't duplicate it." Both
changes are additive (a new optional field, one new key in an existing
response dict) and Module 5's own test suite still passes unmodified.

## Module 7 — Post-Interview Chat

- **Reuses Module 5's AI service, doesn't fork it.** A new method,
  `AIAssistantService.interview_chat_reply()`, is added to the same
  `ai_assistant` singleton every other mode uses — same `_chat()` primitive,
  same Gemini client, same conversation-history handling. There is still
  exactly one place in the codebase that constructs `genai.Client(...)`.
- **Grounding is the interview's own record, not RAG.** A new
  `_interview_context()` helper builds its context entirely from one
  `InterviewSession`'s `role`, `qa_log` (every question, answer, score,
  feedback, and ideal answer), and `final_report` — no resume/RAG lookup,
  since the spec scoped this mode to the interview record itself, and that
  record already has everything it needs.
- **No duplicate interview records.** When the user asks for extra practice
  questions in this chat, the AI just asks and evaluates them
  conversationally in the same reply — there's no call into
  `generate_interview_questions()`/`evaluate_interview_answer()` and no new
  `InterviewSession` row created. This is chat, not another interview.
- **New model**: `InterviewChatMessage` (in the `history` app, since this is
  fundamentally a feature of the interview-history detail page) — one
  `role`/`content`/`created_at` row per turn, `ForeignKey` to
  `InterviewSession` with `on_delete=CASCADE`.
- **Deleting an interview deletes its chat for free.** Because of that
  `CASCADE`, Module 6's existing `interview.delete()` call already deletes
  every chat message for that interview — no new cleanup code was needed
  anywhere, including in Module 6's own delete view, which is untouched.
- **Isolation**: both chat endpoints reuse `history/views.py`'s existing
  `_own_completed_qs(user)` — the exact same ownership rule (must belong to
  `request.user`, must be `completed`) already enforced for view/rename/
  delete. A chat request for another user's interview 404s identically to
  every other history endpoint.
- **Frontend**: a new `InterviewChatPanel` component embedded directly in
  the existing History detail view — no new route, no new nav link. It's a
  self-contained ChatGPT-style thread (message bubbles, optimistic send,
  auto-scroll) scoped to whichever interview is currently open.

### New/changed files in Module 7

- New: `backend/history/models.py`, `backend/history/migrations/0001_initial.py`
  (the `history` app's first model — it previously had none), `backend/history/chat_views.py`,
  `backend/history/admin.py`
- Changed (additive only): `backend/history/serializers.py` (added
  `InterviewChatMessageSerializer`), `backend/history/urls.py` (added the
  `.../chat/` route), `backend/assistant/services.py` (added
  `INTERVIEW_CHAT_SYSTEM`, `_interview_context()`, and
  `interview_chat_reply()` — Module 5's existing prompts, methods, and
  singleton are untouched), `backend/assistant/tests.py` and
  `backend/history/tests.py` (new test classes appended; no existing test
  was modified)
- New: `frontend/src/components/history/InterviewChatPanel.jsx`
- Changed (additive only): `frontend/src/api/historyApi.js` (added
  `getInterviewChat`/`sendInterviewChatMessage`), `frontend/src/pages/History.jsx`
  (renders `InterviewChatPanel` inside the existing detail view, between the
  Q&A review and the delete section)

No route, nav link, or sidebar item was added — the chat lives entirely
inside the page Module 6 already built.

## Module 8 — FastAPI + n8n Integration + Deployment

This module changed the *transport* for AI calls, not the AI logic itself.
Read the "Why this split" note below before the file list if anything here
seems surprising.

### Architecture

```
React  ──HTTP──▶  Django (DRF)  ──HTTP──▶  FastAPI (AI service)  ──SDK──▶  Gemini
                       │                                              ▲
                       └──────────────────HTTP (embeddings)───────────┘
                       │
                       ├──▶ PostgreSQL (all app data: users, resumes, history, chat)
                       └──▶ ChromaDB (vectors only — local dir or networked server)

n8n  ──HTTP──▶  Django's existing authenticated API   (optional orchestration, see below)
```

- **Django** keeps everything it already owned: auth, resume upload/storage,
  PDF extraction, RAG chunking/storage/retrieval/isolation, history, chat
  persistence, and — critically — every prompt template and every piece of
  "who owns what resume" logic. It is still the only thing a browser or n8n
  ever talks to for anything involving the database.
- **FastAPI (`ai_service/`)** is a small, stateless, database-free service
  with exactly one job: take a prompt (or text to embed) from Django and
  call Gemini. It has no models, no auth beyond a shared internal secret,
  and no knowledge of resumes, users, or interviews as concepts.
- **n8n** optionally orchestrates the *existing* Django API from outside —
  it does not run inside the request/response path of any user-facing
  feature.

### Why this split (minimum safe integration points)

Before writing any FastAPI code, I audited Modules 1-7 for every place that
called Gemini directly: three files — `analysis/services.py`,
`assistant/services.py`, `rag/services.py`. In each one, the raw
"send this to Gemini, get a result back" call was already a single,
clearly-bounded function (`analyze_resume_text`, `_chat`, `embed_texts`,
etc.) — everything around it (prompt construction, resume/analysis lookups,
RAG grounding, DB writes) was Django-specific logic that has no reason to
move anywhere.

So the boundary is exactly that: **FastAPI replaced the inside of those
functions, not the functions themselves.** Every function kept its exact
signature, return type, and exception type. Two consequences of that:

1. **Modules 2 and 4 were not touched beyond one line.** Resume upload,
   PDF extraction, chunking, Chroma storage, indexing state, and the
   two-layer isolation check in `retrieve_relevant_chunks` are all
   unchanged — only the one line inside `embed_texts` that called
   `genai.Client()` now calls the AI service instead.
2. **No existing test needed to change.** Every test in Modules 3, 4, 5,
   and 7 mocks at the function boundary (`analyze_resume_text`,
   `embed_texts`, `ai_assistant.xxx_reply`, or `_chat` itself) — none of
   them reach deep enough to know or care whether the real implementation
   talks to Gemini directly or over HTTP. I verified this by re-reading
   every mock target in those four test files before writing any Module 8
   code, specifically to confirm this would hold.

Prompt wording stayed in Django deliberately: prompt engineering is a
product concern that changes often and should stay version-controlled next
to the grounding logic that feeds it, not buried in a "generic" service that
would need redeploying for a wording tweak. FastAPI's structured endpoints
(`/resume-analysis`, `/interview/questions`, `/interview/evaluate`,
`/interview/report`) each take a single pre-formatted `prompt` string and
enforce a known response shape — they don't know what the prompt says.

### What did *not* move to FastAPI (and why)

- **PDF extraction (Module 2)** — needs the uploaded file on disk and
  PyMuPDF; there's no "AI call" in it to extract.
- **Chunking, Chroma reads/writes, indexing state (Module 4)** — this is
  storage and isolation logic tied to Django's `Resume`/`ResumeIndex`
  models; only the embedding *call* moved, not the pipeline around it.
- **Grounding/context-building** (`_resume_context`, `_interview_context`
  in `assistant/services.py`) — these read `ResumeAnalysis`, `Resume`, and
  call `retrieve_relevant_chunks`, all of which need Django's ORM and
  request-scoped `user`. Moving this to FastAPI would mean giving a
  stateless service database access and user-isolation responsibility —
  exactly the kind of scope creep "minimum safe integration points" was
  meant to avoid.
- **Interview/chat/history persistence (Modules 5-7)** — unchanged; FastAPI
  never sees a database.

### FastAPI endpoints (internal only — never called by the browser)

All require header `X-Internal-Api-Key` (matching `AI_SERVICE_INTERNAL_KEY`)
when that key is configured; skipped when it isn't, for local dev convenience.

| Method | Endpoint | Mirrors |
|---|---|---|
| GET | `/health` | — |
| POST | `/chat` | `assistant/services.py::_chat` (Module 5) |
| POST | `/embeddings` | `rag/services.py::embed_texts` (Module 4) |
| POST | `/resume-analysis` | `analysis/services.py::analyze_resume_text` (Module 3) |
| POST | `/interview/questions` | `generate_interview_questions` (Module 5) |
| POST | `/interview/evaluate` | `evaluate_interview_answer` (Module 5) |
| POST | `/interview/report` | `generate_interview_report` (Module 5) |

### n8n: workflow orchestration, not a rewrite

n8n orchestrates the **existing** Django API from outside — it calls
`POST /api/analysis/analyze/` (the same endpoint the React app already
calls) via one imported workflow (`n8n/workflows/resume-analysis-pipeline.json`).
It does not re-implement chunking, embeddings, or ChromaDB access as n8n
nodes, and it is not in the critical path of the normal upload → extract →
index → analyze flow, which still happens automatically inside Django
(Module 2's view, Module 4's signal) exactly as before. n8n is an optional
external trigger — useful for things like an admin re-running analysis for
a user, or a scheduled job — not a replacement for the tested, synchronous
pipeline. See `n8n/README.md` for import/trigger steps.

I considered and rejected having n8n orchestrate the *full* "upload →
extract → chunk → embed → index → analyze" chain step-by-step: Module 4
deliberately has no HTTP endpoint for indexing (its own README explains
why — it's meant to be called in-process by other Django code, not over
HTTP), so there is no safe external seam for n8n to call for that step
without adding new API surface that only n8n would use. Rather than add
that surface just to make an orchestration diagram look complete, the
workflow only covers the one step that already has a stable, authenticated
endpoint doing real work: analysis.

### Docker

```bash
cp backend/.env.example backend/.env        # fill in DB creds, AI_SERVICE_INTERNAL_KEY
cp ai_service/.env.example ai_service/.env  # fill in GEMINI_API_KEY, same AI_SERVICE_INTERNAL_KEY
docker compose up --build
```

This starts: `postgres` (5432), `chroma` (8010→8000 internally), `ai_service`
(8001), `backend` (8000), `frontend` (3000→80), `n8n` (5678). `docker-compose.yml`
overrides a few `backend` env vars (`DB_HOST`, `AI_SERVICE_URL`,
`CHROMA_HTTP_HOST/PORT`) to use Docker's internal service names instead of
`localhost`, since containers reach each other by service name, not the
host's `localhost` — everything else comes from `backend/.env`.

The backend's `docker-entrypoint.sh` runs migrations (and `collectstatic`
when not in `DEBUG`) before starting `gunicorn`.

### Render deployment

`render.yaml` is a Blueprint covering all 5 deployable pieces:

- **Postgres** — Render's managed database (free tier).
- **`interview-assistant-ai-service`** — Docker web service from `ai_service/Dockerfile`.
- **`interview-assistant-chroma`** — the official `chromadb/chroma` image directly (`runtime: image`), with a persistent disk.
- **`interview-assistant-backend`** — Docker web service from `backend/Dockerfile`, wired to the managed Postgres via `DATABASE_URL` and to the other two services via Render's `fromService` env var references.
- **`interview-assistant-n8n`** — the official `n8nio/n8n` image directly, with a persistent disk.
- **`interview-assistant-frontend`** — a native Render **Static Site** (not Docker) — simpler and cheaper for a Vite build than running nginx in a container, which is why `frontend/Dockerfile` is for docker-compose parity only, not what Render actually runs.

After the blueprint deploys: set `GEMINI_API_KEY` (marked `sync: false`,
Render will prompt for it) on the AI service, and copy its generated
`AI_SERVICE_INTERNAL_KEY` value into the backend's `AI_SERVICE_INTERNAL_KEY`
(also `sync: false` — Render generates one independently per service, they
need to be set to the *same* value by hand once).

### Health checks

- `GET /api/health/` (Django) — checks the process is up and the database
  is reachable; used by `backend/Dockerfile`'s `HEALTHCHECK` and Render's
  `healthCheckPath`.
- `GET /health` (FastAPI) — process liveness only, no Gemini call (a real
  Gemini call on every health check would be slow and cost money for no
  benefit — liveness just needs to confirm the process is serving requests).
- Postgres and Chroma use their own standard health checks in `docker-compose.yml`.

### New/changed files in Module 8

- New: `ai_client/` (Django's shared HTTP client to the AI service),
  `ai_service/` (the entire FastAPI app + tests), `docker-compose.yml`,
  `render.yaml`, `backend/Dockerfile`, `backend/docker-entrypoint.sh`,
  `backend/.dockerignore`, `frontend/Dockerfile`, `frontend/nginx.conf`,
  `frontend/.dockerignore`, `n8n/` (workflow + docs)
- Changed: `backend/config/settings.py` (removed direct Gemini config,
  added `AI_SERVICE_URL`/`AI_SERVICE_INTERNAL_KEY`, `CHROMA_HTTP_HOST`/`PORT`,
  `DATABASE_URL` support, WhiteNoise static files, production security
  settings gated behind `not DEBUG`, and now actually calls `load_dotenv()`
  — see the note below), `backend/config/urls.py` (added `/api/health/`),
  `backend/requirements.txt` (`google-genai` removed — moved to
  `ai_service/requirements.txt` — `httpx`/`dj-database-url`/`whitenoise`/
  `gunicorn` added), `backend/rag/services.py`, `backend/analysis/services.py`,
  `backend/assistant/services.py` (internals only — see above)
- Not changed: every view, serializer, URL, model, migration, and test file
  in Modules 1-7. `rag/tests.py` had two harmless references to a setting
  name that no longer exists (`GEMINI_EMBEDDING_DIMENSIONS` in an
  `override_settings(...)` call and a docstring) updated for accuracy —
  Django's `override_settings` doesn't require a setting to pre-exist, so
  this was never a functional issue, just a stale comment/reference.

### A bug fixed along the way

While wiring up `.env` loading for Docker, I found that `python-dotenv` had
been listed in `backend/requirements.txt` since Module 1 but `load_dotenv()`
was never actually called anywhere — `.env` files were never really being
loaded by Django itself; every setting was coming from real environment
variables the whole time (auto-exported by whatever ran the dev server, or
simply unset and falling back to the code's defaults). `settings.py` now
calls `load_dotenv()` for real, so a `backend/.env` file works as documented
for plain local (non-Docker) development. Docker Compose and Render both
inject real environment variables directly, so this doesn't change anything
for those paths.

## Project structure

```
ai_service/          # Module 8: FastAPI AI service (the only place that imports google-genai)
  app/
    main.py, config.py, security.py, gemini.py, schemas.py
    routers/            # health, chat, embeddings, resume_analysis, interview
  tests/
  requirements.txt, Dockerfile, .env.example
n8n/                  # Module 8: importable workflow + setup notes
  workflows/resume-analysis-pipeline.json
docker-compose.yml    # Module 8: local full-stack (postgres, chroma, ai_service, backend, frontend, n8n)
render.yaml           # Module 8: Render Blueprint for all 5 deployable services
backend/
  config/            # Django project settings, urls, wsgi/asgi
  ai_client/         # Module 8: shared HTTP client to the FastAPI AI service
  accounts/          # Module 1: auth app
  resumes/           # Module 2: resume upload + PyMuPDF extraction
  analysis/          # Module 3: resume analysis (calls the AI service since Module 8)
  rag/               # Module 4: chunk/store/retrieve resume text (ChromaDB; embeds via the AI service since Module 8)
  assistant/         # Module 5: one AI-backed service, four modes + interview flow
  history/           # Module 6: browse/rename/delete completed interviews; Module 7: post-interview chat
  manage.py
  requirements.txt
  .env.example
  Dockerfile, docker-entrypoint.sh
frontend/
  src/
    api/                  # axios.js (shared JWT client), resumeApi.js, analysisApi.js, assistantApi.js, historyApi.js
    context/AuthContext.jsx
    components/           # Navbar, ProtectedRoute, AnalysisSection, assistant/ChatPanel, assistant/InterviewPanel, history/InterviewChatPanel
    pages/                 # Signup, Login, Home, Assistant, History, Dashboard (profile), ChangePassword
  .env.example
  Dockerfile, nginx.conf
```

## Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: set DB_NAME/DB_USER/DB_PASSWORD for your Postgres instance,
# or set USE_SQLITE=True to skip Postgres entirely while developing.
# Since Module 8, Django no longer needs a Gemini API key directly — it
# calls the FastAPI AI service instead (see "AI service setup" below).
# Set AI_SERVICE_URL (defaults to http://localhost:8001, correct for local
# dev) and AI_SERVICE_INTERNAL_KEY (must match the AI service's own .env).
# Module 4 (RAG)'s CHROMA_PERSIST_DIR/CHROMA_COLLECTION_NAME have working
# local defaults; CHROMA_HTTP_HOST is only needed for Docker/Render, where
# Chroma runs as its own networked server instead of a local directory.

python manage.py makemigrations   # should report "No changes detected" — all migrations are already hand-written and committed
python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
python manage.py runserver
```

### AI service setup (Module 8 — required for Modules 3/4/5/7 to actually call Gemini)

```bash
cd ai_service
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt   # includes requirements.txt + pytest/httpx for testing

cp .env.example .env
# Set GEMINI_API_KEY (https://aistudio.google.com/apikey) and, if you set
# AI_SERVICE_INTERNAL_KEY in backend/.env, the same value here too.

uvicorn app.main:app --reload --port 8001
```

Runs at `http://localhost:8001`. The Django backend must be pointed at this
via `AI_SERVICE_URL` (defaults to exactly this URL, so plain local dev needs
no changes there). Without this running, anything that calls Gemini —
resume analysis, RAG indexing, the AI Assistant, post-interview chat — will
return `502`.

API will be live at `http://localhost:8000/api/auth/`.

### Endpoints

| Method | Endpoint                        | Auth required | Purpose                          |
|--------|----------------------------------|:---:|-----------------------------------|
| GET    | `/api/health/`                   | No  | Liveness + DB connectivity check (Module 8) |
| POST   | `/api/auth/signup/`             | No  | Create account                    |
| POST   | `/api/auth/login/`              | No  | Get access + refresh tokens       |
| POST   | `/api/auth/logout/`             | Yes | Blacklist refresh token           |
| POST   | `/api/auth/token/refresh/`      | No* | Exchange refresh for new access   |
| GET    | `/api/auth/profile/`            | Yes | Get own name + email              |
| PATCH  | `/api/auth/profile/`            | Yes | Update own name and/or email      |
| POST   | `/api/auth/change-password/`    | Yes | Change own password               |
| POST   | `/api/resumes/upload/`          | Yes | Upload PDF (multipart, field `file`); 409 if one already exists |
| GET    | `/api/resumes/me/`              | Yes | `{has_resume: false}` or `{has_resume: true, resume: {...}}` |
| POST   | `/api/analysis/analyze/`        | Yes | Run (or return existing) Gemini analysis for own resume; `409` if resume isn't processed yet, `502` if Gemini fails |
| GET    | `/api/analysis/me/`             | Yes | `{has_resume, has_analysis, analysis?}` |

\* requires a valid refresh token in the body instead of a header.

Module 4 (RAG) has no HTTP endpoints — see "Design note" above. It does add
one management command:

```bash
python manage.py backfill_rag_index
```

Indexes any already-processed resume that isn't indexed yet (safe to re-run;
already-indexed resumes are skipped).

Module 5 adds:

| Method | Endpoint                            | Auth required | Purpose |
|--------|--------------------------------------|:---:|---------|
| GET    | `/api/assistant/chat/resume-expert/` | Yes | Own conversation history for this mode |
| POST   | `/api/assistant/chat/resume-expert/` | Yes | Send a message, get the assistant's reply |
| GET/POST | `/api/assistant/chat/career-coach/` | Yes | Same as above; POST also accepts an optional `role` |
| GET/POST | `/api/assistant/chat/tutor/`       | Yes | Same shape as Resume Expert |
| GET    | `/api/assistant/interview/status/`   | Yes | Current in-progress interview, else most recent completed one, else `{has_interview: false}` |
| POST   | `/api/assistant/interview/start/`    | Yes | Body `{"role": "..."}`; `409` if resume isn't processed yet; idempotent while one is already in progress |
| POST   | `/api/assistant/interview/answer/`   | Yes | Body `{"answer": "..."}`; evaluates the current question, advances, generates the final report on the last one |

Module 6 adds:

| Method | Endpoint                              | Auth required | Purpose |
|--------|-----------------------------------------|:---:|---------|
| GET    | `/api/history/interviews/`              | Yes | List the user's completed interviews (title, role, date, score, status) |
| GET    | `/api/history/interviews/<id>/`         | Yes | Full detail: questions, qa_log, final_report |
| PATCH  | `/api/history/interviews/<id>/`         | Yes | Rename (body `{"title": "..."}`); doesn't affect the completion date |
| DELETE | `/api/history/interviews/<id>/`         | Yes | Delete the interview and all its data |
| GET    | `/api/history/interviews/<id>/chat/`    | Yes | This interview's post-interview chat history |
| POST   | `/api/history/interviews/<id>/chat/`    | Yes | Send a message, get the assistant's reply (grounded in that interview's own record) |

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env   # points the app at the backend above
npm run dev
```

App runs at `http://localhost:5173`.

> Prefer not to run six things in six terminals? `docker compose up --build`
> from the project root starts everything (frontend included) at once — see
> the **Docker** section under Module 8 above.

## Running the backend tests

```bash
cd backend
python manage.py test accounts resumes analysis rag assistant history
```

Since Module 8, this needs the AI service reachable at `AI_SERVICE_URL` for
tests to *collect and run at all* only insofar as `assistant/services.py`
etc. import successfully — the tests themselves still mock at the same
function boundaries as before (`analyze_resume_text`, `embed_texts`,
`ai_assistant.xxx_reply`), so they don't actually make HTTP calls to the AI
service and don't require it to be running. Nothing about the test suite's
behavior changed; see Module 8's section above for exactly why.

## Running the AI service tests

```bash
cd ai_service
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Every router's tests mock `gemini.generate_text` / `generate_structured` /
`embed_texts` directly (same approach as Modules 3/4/5/7's Django tests) —
no real Gemini calls, no `GEMINI_API_KEY` needed to run them. Each test
file covers: the internal-API-key check (401 without it, 401 with the
wrong one), a mocked success path asserting the exact request/response
shape, and a mocked Gemini failure returning `502`.


`accounts` exercises: signup validation (password match, duplicate email,
weak password), login success/failure, profile isolation between two
different users, profile updates, password changes, and refresh-token
blacklisting on logout.

`resumes` exercises: upload requires auth, a hand-built-but-valid minimal PDF
uploads and extracts real text via PyMuPDF, non-PDF extensions are rejected,
a `.pdf`-named file with spoofed `content_type` but non-PDF bytes is still
rejected (magic-byte check), oversized files are rejected, a second upload
for the same user gets `409`, and `/me/` never returns another user's resume.

`analysis` exercises: auth is required, analyzing without a resume returns
`404`, analyzing before the resume finishes processing returns `409`,
a successful analysis (Gemini itself is mocked — these are unit tests, not
a live API integration test) is stored and returned with the full structured
shape, a second `analyze/` call reuses the stored result instead of calling
Gemini again, a Gemini failure is caught and stored as `status: "failed"`
with a `502` response, and `/me/` never returns another user's analysis.

`rag` exercises: the chunker's overlap/coverage behavior directly (no mocking
needed — pure logic); indexing stores the right number of chunks with correct
`user_id`/`resume_id` metadata in a real (temp-directory) ChromaDB instance;
re-indexing identical content is a no-op (Gemini's embed call isn't even
invoked a second time, and no duplicate vectors are stored); an embedding
failure is caught and recorded as `status: "failed"` rather than propagating
as a crash; retrieval for one user never returns another user's chunks even
when both have matching top-k results; a resume with no index row yet gets
indexed lazily on first retrieval; and the `post_save` signal indexes a
resume automatically the moment its status becomes `processed`. As with
`analysis`, Gemini's embedding calls are mocked — ChromaDB itself is not
mocked, since it's a local embedded library with no network dependency, so
those tests exercise the real storage/query/isolation logic.

`assistant` exercises: chat history is empty before any message, empty
messages are rejected, a successful reply stores both the user's message and
the assistant's reply (Gemini itself is mocked at the `ai_assistant`
boundary — one level higher than Module 3/4's mocks, since the point of
these tests is `assistant/views.py`'s own logic, not re-testing Gemini
call mechanics `services.py` already shares with those modules), a Gemini
failure returns `502` *and* stores nothing (no half-written turn), Career
Coach persists an optional `role` onto the session, two users never see each
other's chat history, starting an interview without a role or without a
processed resume is rejected, starting one twice returns the same interview
instead of creating a second (both at the application level and via a
real — not mocked — attempt to violate the partial unique DB constraint
directly), a full interview run advances question-by-question to a
generated final report, an evaluation failure returns `502` *without*
advancing the question index or logging a partial answer, and two users'
interviews never cross.

Also in `assistant`: `interview_chat_reply()`'s grounding is tested directly
against `_chat()` (mocked) — a completed `InterviewSession`'s role, one
question/answer/score/feedback pair, and its weak-areas summary are all
asserted present in the grounded message passed to Gemini, with no DB or
Gemini call needed for that specific test.

`history` exercises: an in-progress interview never appears in the list or
is reachable by detail/rename/delete (only `completed` ones are), a
completed interview's title falls back to its role when never renamed, the
list orders most-recently-completed first, renaming changes the title
without changing `updated_at` (asserted directly against the stored value,
not just the response), an overly long title is rejected and leaves the
stored title unchanged, renaming to blank resets the display back to the
role fallback, deleting removes the row entirely, and — across every one of
list/detail/rename/delete — a second user gets a plain `404` for the first
user's interview, never a `403` that would confirm it exists.

Also in `history` (Module 7): chat history is empty before any message, a
chat request for an in-progress or nonexistent interview 404s exactly like
history's other endpoints, an empty message is rejected, a successful
exchange stores both turns and returns the assistant's reply (Gemini mocked
at the `ai_assistant` boundary, same approach as the `assistant` app's own
chat tests), a Gemini failure returns `502` and stores nothing, deleting the
parent interview deletes its chat messages too (exercising the real
`on_delete=CASCADE`, not just asserting the field exists), and a second user
gets `404` on both reading and posting to the first user's chat — with the
mocked `interview_chat_reply` asserted as *never called* in that case, not
just the response checked.

> **A note on this delivery:** the sandbox this code was written in has no
> network access, so `pip install`/`npm install` couldn't run here and none
> of the six Django test suites, nor `ai_service`'s own pytest suite, could
> actually be executed in this environment.
> What *was* verified in-sandbox: every Python file passes `python -m
> py_compile`, every JS/JSX file was syntax/bundle-checked with `esbuild`,
> and (for Module 4) the dependency-free `chunk_text` logic was run
> standalone to confirm its overlap math. Module 5's service layer
> (`assistant/services.py`) follows the same `google-genai` structured-
> output and multi-turn `contents` patterns already used in Modules 3 and 4,
> but — like those modules' Gemini calls — it is unexecuted against the
> real API here. The interview flow's core rules (theory-only, 10-15
> questions, one active interview per user) are also enforced by *validated,
> unexecuted* logic: the Pydantic `Field(min_length=10, max_length=15)`
> constraint and the partial unique DB constraint are both standard,
> well-documented mechanisms, but I could not run a real Gemini call to
> confirm the model reliably returns a count in that range on the first try
> (the code retries via a normal `AIServiceError` → `502` on validation
> failure, not a silent retry loop, so a persistent miss surfaces as an
> error rather than hanging). Module 6 has no external API calls at all —
> it's pure Django ORM/DRF logic reading Module 5's own data — so it carries
> the least amount of "unexecuted but should work" risk of any module so
> far; the `QuerySet.update()`-doesn't-trigger-`auto_now` behavior it
> depends on for the rename feature is standard, explicitly documented
> Django behavior, not an assumption. Module 7's `interview_chat_reply()`
> reuses `_chat()` exactly as written for Modules 5's other three
> conversational modes, so it carries the same risk profile as those —
> no new Gemini call pattern was introduced. Please still run the full test
> suite and try a real chat message, a real interview start → answer →
> report → rename → delete flow, and a real post-interview chat message
> yourself:
>
> ```python
> python manage.py shell
> >>> from django.contrib.auth import get_user_model
> >>> from assistant.models import InterviewSession
> >>> from assistant.services import ai_assistant
> >>> user = get_user_model().objects.get(email="you@example.com")
> >>> ai_assistant.resume_expert_reply(user, [], "What's my ATS score and why?")
> >>> interview = InterviewSession.objects.filter(user=user, status="completed").first()
> >>> ai_assistant.interview_chat_reply(interview, [], "What was my weakest answer and how could I improve it?")
> ```
>
> before treating Modules 5, 6, and 7 as verified. If anything fails —
> including a real Gemini error, a validation error if the model returns
> fewer than 10 questions, or a chat reply that doesn't reference the
> interview's actual questions — paste it back and I'll fix it.
>
> **Module 8 specifically:** none of its new dependencies (`fastapi`,
> `uvicorn`, `httpx`, `dj-database-url`, `whitenoise`, `gunicorn`) were
> importable in this sandbox either, so — same as every module before it —
> what's verified here is `python -m py_compile` across every backend and
> `ai_service` file, `esbuild` across the frontend, and separately, YAML/JSON
> syntax validation for `docker-compose.yml`, `render.yaml`, and the n8n
> workflow file (all three parse cleanly, checked directly with `yaml.safe_load`/
> `json.load` in this sandbox — that confirms syntax, not that Docker or
> Render will accept every field). The one thing I'm most confident about
> without having run it: the "existing tests don't need to change" claim
> above isn't a guess — I read every mock target in `analysis/tests.py`,
> `rag/tests.py`, `assistant/tests.py`, and `history/tests.py` before writing
> a line of `ai_service/` code, specifically to confirm the boundary I chose
> wouldn't require touching them. The thing I'm least confident about: I
> have never run `docker compose up` against this exact set of five
> Dockerfiles/images together, so a real build could still surface something
> a syntax check can't — a wrong path, a missing system library, a port
> collision. Please run, in this order:
>
> ```bash
> # 1. Confirm nothing in Modules 1-7 broke
> cd backend && pip install -r requirements.txt && python manage.py test accounts resumes analysis rag assistant history
>
> # 2. Confirm the AI service works on its own
> cd ../ai_service && pip install -r requirements-dev.txt && pytest
>
> # 3. Confirm the whole stack builds and talks to itself
> cd .. && cp backend/.env.example backend/.env && cp ai_service/.env.example ai_service/.env
> # fill in GEMINI_API_KEY and a matching AI_SERVICE_INTERNAL_KEY in both files
> docker compose up --build
> # then: sign up, upload a resume, and watch it reach "processed" —
> # that exercises Django -> AI service -> Gemini and Django -> Chroma (networked) end to end
> ```
>
> before treating Module 8 — or Docker/Render readiness generally — as
> verified. If step 3 fails, the error will point at exactly one of five
> containers; paste it back and I'll fix that one.

## Security notes

- Passwords are hashed with Django's default PBKDF2 hasher — never stored or
  logged in plaintext.
- `AUTH_PASSWORD_VALIDATORS` rejects short, common, and fully-numeric
  passwords at signup and change-password time.
- Refresh tokens are blacklisted on logout and rotated on every refresh
  (`ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION`), so a stolen refresh
  token can't be replayed after the user logs out.
- CORS is locked to the frontend's origin via `CORS_ALLOWED_ORIGINS`.
- User isolation is structural, not just a permission check: profile and
  password endpoints always resolve to `request.user`, there is no endpoint
  that takes another user's ID.
- The same structural isolation applies to Module 3: `analyze/` and `/me/`
  always resolve through `request.user`'s own `Resume` row — there is no
  resume-ID or user-ID parameter anywhere in the `analysis` app.
- The ATS score and every other Gemini-generated field are inherently
  probabilistic model output — they're labeled as an estimate in the UI and
  should be treated as a helpful signal, not an authoritative grade.
- `GEMINI_API_KEY` is read from the environment and never sent to the
  frontend or included in any API response.
- Module 4's isolation is enforced twice, not once: ChromaDB's `where`
  filter restricts a query to the requesting user's `user_id` and
  `resume_id` before anything is returned, and every returned chunk's
  metadata is checked again in Python — a mismatch raises rather than being
  silently dropped, on the theory that a cross-user leak should fail loudly,
  not quietly.
- Vector data lives in `CHROMA_PERSIST_DIR` (default: `backend/chroma_data/`)
  as local files, analogous to `media/` for uploaded PDFs — treat it as data
  to back up/secure the same way you would the database, not as disposable
  cache.
- Module 5's isolation follows the same structural pattern: every chat and
  interview endpoint resolves only through `request.user`, and no view
  anywhere in `assistant/` accepts a session, message, or interview ID from
  the client. The one-active-interview-per-user rule is enforced at the
  database level (a partial unique constraint), not only in application
  code, so it holds even under concurrent requests.
- The AI Tutor mode is intentionally not grounded in the resume — it
  explains concepts and evaluates practice answers generically, per spec.
  Resume Expert, Career Coach, and the Interviewer all use the same
  grounding rule, so "never invent resume information" is enforced in one
  place (`_GROUNDING_RULE` in `assistant/services.py`) rather than
  per-mode.
- Module 6's isolation query (`history/views.py::_own_completed_qs`) filters
  by `user` and `status=completed` together in a single queryset used by
  every view in the app — there is no code path that constructs a query
  without both conditions, so there's nothing to accidentally forget on a
  future edit.
- Every Module 6 "not found" response — whether the interview truly doesn't
  exist, belongs to someone else, or simply isn't completed yet — returns
  the same `404`. It never returns `403`, which would leak the fact that
  *something* exists at that ID even if the requester can't touch it.
- Module 7's chat endpoints reuse that exact same rule — `history/chat_views.py`
  calls the same `_own_completed_qs(user)` helper `history/views.py` already
  defines, rather than reimplementing ownership logic a second time.
  `InterviewChatMessage.interview` uses `on_delete=CASCADE`, so deleting an
  interview through Module 6's existing endpoint removes its chat messages
  as a direct database consequence — there's no separate cleanup step that
  could be forgotten or fail independently.
- **Module 8**: the AI service has no user accounts, no per-user data, and
  no concept of "which user is asking" — it only ever sees a prompt or a
  batch of texts, already scoped/filtered by Django before the request is
  made. It is not reachable from the browser; `AI_SERVICE_URL` in
  `docker-compose.yml`/`render.yaml` points at an internal service address,
  never a public one. `AI_SERVICE_INTERNAL_KEY` is a defense-in-depth layer
  on top of that network isolation, not a substitute for it — set it in
  every shared or deployed environment, since "local dev convenience" (the
  check is skipped when the key is blank) is the only case where skipping
  it is reasonable.
- `GEMINI_API_KEY` now lives only in the AI service's environment — it was
  removed from `backend/.env.example` entirely rather than left as an
  unused, confusing duplicate. Django cannot leak a key it no longer holds.
- Every secret in this project (`DJANGO_SECRET_KEY`, `AI_SERVICE_INTERNAL_KEY`,
  `N8N_BASIC_AUTH_PASSWORD`, `GEMINI_API_KEY`) is read from an environment
  variable with either no default or an obviously-not-for-production default
  (`dev-only-secret-change-me`) — never hardcoded, and `render.yaml` marks
  the ones Render should generate or prompt for (`generateValue: true` /
  `sync: false`) rather than shipping a value in the blueprint itself.
- Production security settings (`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`,
  HSTS, etc.) are gated behind `not DEBUG`, so a misconfigured `DJANGO_DEBUG`
  is the one variable that would silently leave production running with
  development-level settings — worth double-checking is set to `False` on
  any real deployment, since every other production hardening in this
  project depends on that flag being correct.
