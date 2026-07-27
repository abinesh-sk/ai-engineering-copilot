# AI Engineering Copilot — Build Progress

> Reference doc: `AI_Engineering_Copilot_Design_Document_v2.docx` (Project files)
> This file is the single source of truth for where the implementation stands.
> If a chat session runs out of context, upload/point Claude to this file to resume.

---

## How this file works

- Updated at the end of every implementation day (or session, if a day spans multiple chats).
- Each entry logs: what was built, what concepts were taught, what's left.
- "Current Status" at the top always reflects the *latest* state — read that first if resuming.
- Deviations from the original design doc are logged explicitly, since the doc itself won't be edited during implementation.

---

## Current Status

**Last completed:** Day 5 — Backend deployed to Render (free tier), React frontend skeleton deployed to Vercel, both talking to each other in production
**Next up:** Day 6 — Local RAG script: load sample company-policy documents, chunk, embed, store in pgvector
**Blocking issues:** None

---

## Learning Log (concepts covered so far)

- **Domain-based vs. layer-based folder structure** — folder boundaries as enforced module boundaries (Day 1)
- **FastAPI vs. uvicorn** — FastAPI is routing/validation logic; uvicorn is the actual ASGI server process (Day 1)
- **`/health` endpoint pattern** — used later by hosting platforms (Render/Fly) to check process liveness (Day 1)
- **Why Neon (hosted Postgres) locally too** — dev and prod hit the same DB shape, no "works on my machine" surprise (Day 1)
- **pgvector as a Postgres extension** — adds a `vector` column type + similarity operators directly into SQL; enabled now, used starting Day 19 (Day 1)
- **`.env` + `.gitignore`** — secrets never committed to git; `python-dotenv` loads them at runtime (Day 1)
- **SQLAlchemy `engine`** — a connection factory/pool, not an open connection itself (Day 1)
- **ORM models as schema-in-Python** — a class maps to a table; lets you manipulate rows as objects instead of raw SQL (Day 2)
- **Why migrations, not just `create_all()`** — schema history needs to support *altering* existing tables with data in them, not just creating new ones; Alembic migrations are the real source of truth for schema evolution (Day 2)
- **UUID primary keys vs. auto-increment integers** — avoids ID collisions across API + worker processes, doesn't leak row counts (Day 2)
- **Trace vs. TraceSpan (two-table split)** — Trace = one execution; TraceSpan = one sub-step (retrieval, llm_call, etc.); split lets later stages query specific span data directly instead of parsing a JSON blob (Day 2)
- **`raw_data` as flexible JSON on spans** — span shapes differ by type; Feature Extraction (Day 10+) is what turns this mess into clean columns, not the ingestion layer (Day 2)
- **How Alembic autogenerate works** — diffs `Base.metadata` (what models say) against actual DB state, writes the difference as `upgrade()`/`downgrade()` — reviewed, not blindly trusted (Day 2)
- **Pydantic schemas vs. SQLAlchemy models** — SQLAlchemy defines the DB row shape; Pydantic defines what a client may send in / what gets returned — kept separate so clients can't set server-generated fields like `id`/`status` (Day 3)
- **`Depends()` / dependency injection for DB sessions** — `get_db()` yields a fresh session per request and always closes it via `finally`, even on error (Day 3)
- **Fast synchronous ingestion, nothing slow in the request path** — POST /traces only validates + writes + returns; no LLM/vector work happens here (Section 7.1, Day 3)
- **Why a clean 404 matters** — predictable error contracts vs. leaking stack traces to callers (Day 3)
- **PowerShell shell-quoting pitfalls** — backtick line continuation breaks silently on trailing whitespace; manually escaping JSON in `curl.exe -d` is fragile — `Invoke-RestMethod` with a hashtable, or testing via `/docs`, avoids this entirely (Day 3)
- **RQ (Redis Queue) basics** — `enqueue()` pushes a function reference + args onto a Redis list; a separate `Worker` process pulls jobs off and executes them — this *is* the producer/consumer pattern from Section 8.1, Redis is just the handoff point (Day 4)
- **Enqueue by string import path, not function reference** — passing `"app.core.jobs.process_trace_job"` instead of importing the function directly keeps `trace/router.py` from needing to know anything about how jobs are implemented; same one-directional module-boundary discipline as Section 6.2 (Day 4)
- **Why `str(trace.id)` before enqueueing** — RQ serializes job args to store them in Redis; SQLAlchemy's UUID objects don't serialize cleanly by default, so cast to string first (Day 4)
- **Self-contained env loading per module** — `queue.py` calls its own `load_dotenv()` rather than relying on `database.py` having already loaded it via import order; avoids a fragile hidden dependency on import sequence (Day 4)
- **`os.fork()` and Windows** — RQ's default `Worker` forks a child process per job for crash isolation; `os.fork()` doesn't exist on Windows, so local dev uses `SimpleWorker` (in-process, no fork) instead — production on Render/Fly (Linux) can use the default `Worker` (Day 4)
- **`AbandonedJobError`** — when a worker dies mid-job (e.g. the fork crash), RQ detects the orphaned job on the next worker startup and moves it to the failed registry rather than leaving it stuck — queue self-healing, not a bug (Day 4)
- **Free-tier reality check (2026):** neither Render nor Fly.io offers a genuinely free *second* process as a separately deployed service anymore (Render's Background Worker service type is $7+/month; Fly.io dropped its free tier entirely for new accounts). Solved by running the worker as a second process *inside* the same free web service container via the start command — which is actually closer to Section 8.1's original wording ("a second process inside the same deployed container") than paying for a dedicated worker service would have been (Day 5)
- **CORS (Cross-Origin Resource Sharing)** — browsers block cross-origin fetches by default; the server must explicitly allow the calling origin via response headers. Used `allow_origins=["*"]` temporarily until the real Vercel URL existed, then tightened to that exact origin — same "loosen only as long as necessary" instinct as any other security default (Day 5)
- **Root Directory setting on Render/Vercel** — both platforms needed to be told the app actually lives in a subfolder (`backend/`, `frontend/`) rather than the repo root, since the git repo wraps both apps as siblings (Day 5)
- **Vite env vars (`VITE_` prefix + `import.meta.env`)** — only vars prefixed `VITE_` are exposed to browser code at build time; swapping `.env.local` (dev) for a platform env var (prod) changes the API target with zero code changes — same interface-swapping instinct as `LLMProvider`, applied to config (Day 5)
- **Platform value fields aren't `.env` file parsers** — Render/Vercel env var value boxes take the literal string typed in, quotes and all; copying a display string like `KEY="value"` verbatim (quotes included) breaks the connection, since the quotes become part of the literal value (Day 5)

---

## Day-by-Day Log

### Day 1 — Repo structure, Python env, FastAPI hello-world, Postgres connection
**Status:** ✅ Complete
**Design doc reference:** Section 17.1
**Learning objective (per design doc):** Why structure by domain (`trace/`, `evidence/`) instead of by technical layer

**What was built:**
- Repo at `C:\Users\kirut\desktop\ai-engineering-copilot\backend`
- Domain folders under `app/`: `core/`, `trace/`, `evidence/`, `reasoning/`, `replay/`, `historical/`
- Python venv (`venv/`) with `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `psycopg2-binary`, `python-dotenv` (frozen to `requirements.txt`)
- `app/main.py` — FastAPI app with `/`, `/health`, and temporary `/db-check` endpoints
- Neon project `ai-engineering-copilot` (database `neondb`), pgvector extension enabled via `CREATE EXTENSION IF NOT EXISTS vector;`
- `.env` with `DATABASE_URL`, `.gitignore` excluding `venv/`, `.env`, `__pycache__/`
- `app/core/database.py` — SQLAlchemy engine + `check_connection()` helper

**Verified:** `GET /db-check` → returned live PostgreSQL 18.4 version string from Neon. Connection confirmed end to end.

**Note:** `/db-check` in `main.py` is a temporary sanity-check endpoint — fine to leave for now, will likely be removed or moved once real endpoints exist (Day 3).

---

### Day 2 — SQLAlchemy models, first Alembic migration
**Status:** ✅ Complete
**Design doc reference:** Section 17.1
**Learning objective (per design doc):** Migrations as the source of truth for schema

**What was built:**
- `app/core/models.py` — shared `Base`, `Organization`, `User`, `Application` models, all with UUID PKs; `User`/`Application` carry `org_id` as a real FK (Section 10.3 discipline)
- `app/trace/models.py` — `Trace` (status lifecycle: `ingested` → `extracted` → `evidence_generated` → `diagnosed`) and `TraceSpan` (span_type, sequence, `raw_data` JSON), linked via FK with cascade delete
- Alembic initialized (`alembic/`, `alembic.ini`); `alembic/env.py` wired to read `DATABASE_URL` from `.env` (moved `config.set_main_option` to run unconditionally for both online/offline modes) and to import `Base` + all domain models so autogenerate can see every table
- First migration (`4acecc740be0`) generated and applied: creates `organizations`, `applications`, `users`, `traces`, `trace_spans`; also drops Neon's placeholder `playing_with_neon` demo table

**Verified:** `alembic upgrade head` ran cleanly against Neon; tables confirmed present in Neon Console → Tables.

**Note:** Neon ships a sample table (`playing_with_neon`) on every new project — autogenerate correctly flagged it as not in our models and dropped it. Not a bug, just Neon's default demo data.

---

### Day 3 — POST /api/v1/traces, GET /api/v1/traces/{id}
**Status:** ✅ Complete
**Design doc reference:** Section 17.1, Section 7.1
**Learning objective (per design doc):** What makes an API payload schema good for a system that must evolve

**What was built:**
- `backend/seed.py` — one-time script, creates one `Organization` ("Personal Org") and one `Application` ("rag_test_app"); prints their UUIDs for use in test requests
- `app/core/database.py` — added `SessionLocal` + `get_db()` dependency for per-request DB sessions
- `app/trace/schemas.py` — Pydantic schemas: `TraceCreate`/`SpanIn` (inbound, no server-generated fields), `TraceOut`/`SpanOut` (outbound, `from_attributes = True` to read straight off SQLAlchemy objects)
- `app/trace/router.py` — `POST /api/v1/traces` (creates trace + nested spans, status defaults to `"ingested"`) and `GET /api/v1/traces/{trace_id}` (404 if not found)
- Wired `trace_router` into `app/main.py`

**Verified:**
- `POST /api/v1/traces` with a real query + 2 spans (retrieval, llm_call) → `201`, full trace object returned with server-generated `id` and `created_at`
- `GET /api/v1/traces/{id}` with the real ID → same trace returned correctly, spans nested
- `GET /api/v1/traces/{id}` with a bogus UUID → clean `404 {"detail": "Trace not found"}`, no stack trace leak

**Deviation logged:** none functionally — see Deviations section for the PowerShell testing workaround.

### Day 4 — Redis (Upstash) + minimal background worker
**Status:** ✅ Complete
**Design doc reference:** Section 17.1, Section 8.1
**Learning objective (per design doc):** Decoupling ingestion from processing; producer/consumer pattern

**What was built:**
- Upstash Redis database created (`ai-engineering-copilot`, Regional); TCP connection string saved as `REDIS_URL` in `.env` (the `rediss://` native connection string, not the REST URL/token pair — `redis-py`/`rq` need a socket-style connection, not HTTP REST)
- `app/core/queue.py` — `redis_conn` (Redis client) + `job_queue` (RQ `Queue`), with its own `load_dotenv()` call so it doesn't depend on import order relative to `database.py`
- `app/core/jobs.py` — `process_trace_job(trace_id: str)`, a plain top-level function (required so RQ can import/pickle it by module path) that currently just logs receipt
- `trace/router.py` — POST /api/v1/traces now calls `job_queue.enqueue("app.core.jobs.process_trace_job", str(trace.id))` immediately after commit/refresh, before returning
- `app/core/worker.py` — worker entry script; uses RQ's `SimpleWorker` (in-process, no `os.fork()`) instead of the default `Worker`, since `os.fork()` doesn't exist on Windows

**Verified:** Ran `python -m app.core.worker` in a second terminal, POSTed a trace via `/docs` in the browser, watched the worker log `[worker] Received job for trace_id: <uuid>` and `Job OK` in real time. Confirmed the full loop: API enqueues → Upstash Redis holds the job → worker picks it up → runs the function.

**Note:** Confirmed `.env` is not double-loaded incorrectly — Python only runs a module's top-level code once per process, so multiple `load_dotenv()` calls across files are safe, not wasteful.

---

### Day 5 — Deploy backend + frontend skeleton
**Status:** ⬜ Not started

### Day 5 — Deploy backend + frontend skeleton
**Status:** ⬜ Not started

### Day 5 — Deploy backend + frontend skeleton
**Status:** ✅ Complete
**Design doc reference:** Section 17.1, Section 9
**Learning objective (per design doc):** The deployment topology; why frontend and backend deploy independently

**What was built:**
- Git repo initialized at project root (`ai-engineering-copilot/`, wraps `backend/` and `frontend/` as siblings), pushed to GitHub (`abinesh-sk/ai-engineering-copilot`)
- `app/main.py` — added stubbed `GET /api/v1/dashboard` endpoint (hardcoded zeros + message, real aggregation comes Section 16.3) and `CORSMiddleware`
- **Backend deployed to Render** (free Web Service tier): Root Directory `backend`, Start Command `python -m app.core.worker & uvicorn app.main:app --host 0.0.0.0 --port $PORT` — runs API + worker as two processes inside one free container, since neither Render's Background Worker service nor Fly.io are actually free for a second process anymore. `DATABASE_URL` / `REDIS_URL` set as Render environment variables (not committed). Live at `https://ai-engineering-copilot.onrender.com`
- **Frontend scaffolded** with Vite + React + TypeScript + ESLint at `frontend/`; `App.tsx` fetches `/api/v1/dashboard` and renders it; `VITE_API_URL` read via `import.meta.env`, set locally in `.env.local` (gitignored) and as a Vercel environment variable in production
- **Frontend deployed to Vercel**: Root Directory `frontend`, auto-detected Vite preset, `VITE_API_URL` set to the real Render URL. Live at `https://ai-engineering-copilot-nine.vercel.app`
- CORS tightened from `allow_origins=["*"]` to the exact Vercel origin once it existed

**Verified:**
- Render logs show both the worker (`*** Listening on default...`) and uvicorn (`Uvicorn running on http://0.0.0.0:10000`) starting inside the same deploy
- POSTed a trace to the live Render `/api/v1/traces` via `/docs` → `201 Created` → worker log showed `[worker] Received job for trace_id: ...` → `Job OK` — full ingestion → queue → worker loop confirmed in production, not just locally
- Vercel URL loads and correctly displays live data fetched from the Render URL (not local) — both public deployments talking to each other over the internet

**Deviation logged:** Design doc / Section 9 table lists Render or Fly.io without specifying process topology in detail; both platforms' free tiers changed since the doc was written (2026) — worker now runs in-process alongside the API rather than as a separately deployed service, to preserve $0/month cost. See Deviations section.

---

### Day 6 — Local RAG script: load, chunk, embed, store in pgvector
**Status:** ⬜ Not started

### Day 7 — Wire retrieval + prompt + Groq LLM call; POST full trace
**Status:** ⬜ Not started

### Day 8 — Deliberately broken scenarios (failure injection)
**Status:** ⬜ Not started

### Day 9 — Buffer / catch-up
**Status:** ⬜ Not started

### Day 10 — Feature Extraction: retrieval metrics
**Status:** ⬜ Not started

### Day 11 — Feature Extraction: prompt/context metrics
**Status:** ⬜ Not started

### Day 12 — Feature Extraction: latency/cost; wire into worker
**Status:** ⬜ Not started

### Day 13 — Buffer / catch-up
**Status:** ⬜ Not started

### Day 14 — Evidence table + producer interface + Retriever Evidence Producer
**Status:** ⬜ Not started

### Day 15 — Prompt Evidence Producer
**Status:** ⬜ Not started

### Day 16 — LLM Evidence Producer (deterministic groundedness heuristic)
**Status:** ⬜ Not started

### Day 17 — Wire all producers into worker pipeline
**Status:** ⬜ Not started

### Day 18 — Buffer; optional 4th producer stub
**Status:** ⬜ Not started

### Day 19 — HistoricalIncidents table + pgvector embedding step
**Status:** ⬜ Not started

### Day 20 — pgvector similarity search + seed historical incidents
**Status:** ⬜ Not started

### Day 21 — LLMProvider interface + Groq impl + Reasoning prompt template
**Status:** ⬜ Not started

### Day 22 — Wire Reasoning into worker; test against broken scenarios
**Status:** ⬜ Not started

### Day 23 — Buffer; tighten prompt template
**Status:** ⬜ Not started

### Day 24 — ReplayAdapter interface, ReplayResult model, ReplayExecutions table
**Status:** ⬜ Not started

### Day 25 — Implement LocalReplayAdapter
**Status:** ⬜ Not started

### Day 26 — ReplayComparisons; reuse Reasoning for explanation
**Status:** ⬜ Not started

### Day 27 — Full replay loop test end-to-end
**Status:** ⬜ Not started

### Day 28 — Trace Explorer page (frontend)
**Status:** ⬜ Not started

### Day 29 — Replay split-screen page + minimal Dashboard
**Status:** ⬜ Not started

### Day 30 — Final pass: cold-deploy test, README, self-demo
**Status:** ⬜ Not started

---

## Deviations from Design Doc

- **Testing tool:** Design doc mentions "curl/Postman" for Day 3 validation. `curl.exe` with manually-escaped JSON in PowerShell proved too fragile (backtick line continuation + quote escaping both broke). Settled on testing via FastAPI's `/docs` (Swagger UI) as the primary method, with `Invoke-RestMethod` + PowerShell hashtables as the terminal-native alternative. No functional impact — just a Windows/PowerShell-specific tooling note for future days.
- **RQ `Worker` vs `SimpleWorker`:** RQ's default `Worker` forks a child process per job (`os.fork()`), which doesn't exist on Windows. Local dev worker uses `SimpleWorker` (in-process execution, no crash isolation between jobs) instead. Production deploy (Day 5, Render/Fly — Linux containers) can switch back to the default `Worker` for proper crash isolation; worth revisiting then rather than assuming `SimpleWorker` is the permanent choice.
- **Worker deployment topology (Day 5):** neither Render's Background Worker service type nor Fly.io offer a genuinely free tier for a second deployed service as of 2026 (Render worker: $7+/month; Fly.io: no free tier for new accounts). Deviation: worker runs as a second process inside the same free Render web service container, started via the service's Start Command (`python -m app.core.worker & uvicorn ...`), rather than as its own deployed service. This is arguably *more* faithful to Section 8.1's original wording than the alternative would have been, but is logged here since it wasn't an explicit design doc decision at the time it was written. If Render/Fly pricing changes again, or the worker's load grows enough to need real isolation, revisit this.

---

## Environment / Setup Notes

- **Repo path:** `C:\Users\kirut\desktop\ai-engineering-copilot\backend`
- **Activate venv:** `venv\Scripts\activate` (from `backend/`)
- **Run server:** `uvicorn app.main:app --reload` (from `backend/`, venv active)
- **Local URLs:** `http://127.0.0.1:8000` (root), `/health`, `/docs` (interactive API explorer), `/db-check` (temp)
- **DB:** Neon project `ai-engineering-copilot`, database `neondb`, pgvector enabled
- **Queue:** Upstash Redis database `ai-engineering-copilot` (Regional)
- **Env vars required:** `DATABASE_URL`, `REDIS_URL` in `backend/.env` (not committed — see `.gitignore`) — use the TCP `rediss://` connection string from Upstash, not the REST URL/token pair
- **Run worker (separate terminal, venv active, from `backend/`):** `python -m app.core.worker`
- **Deployed backend (Render, free tier):** `https://ai-engineering-copilot.onrender.com` — Root Directory `backend`, env vars `DATABASE_URL`/`REDIS_URL` set in Render dashboard, sleeps after ~15 min idle (cold start on next request)
- **Deployed frontend (Vercel):** `https://ai-engineering-copilot-nine.vercel.app` — Root Directory `frontend`, env var `VITE_API_URL` set in Vercel dashboard to the Render URL above
- **GitHub repo:** `abinesh-sk/ai-engineering-copilot` — root wraps `backend/` and `frontend/` as siblings; personal design docs (`.docx`/`.md` planning files) deliberately excluded via root `.gitignore`, kept local-only
- **Frontend local dev:** `cd frontend && npm run dev` (Vite, default port 5173); needs `frontend/.env.local` with `VITE_API_URL=http://127.0.0.1:8000` and local backend running
- **Deployment status:** live in production as of Day 5 (see deployed URLs above)
- **Seed data:** `python seed.py` (from `backend/`) creates one Organization + one Application, prints their UUIDs — needed for any trace POST test. Re-run only if the DB is reset.
- **Testing endpoints on Windows:** use `http://127.0.0.1:8000/docs` (Swagger UI) — avoids PowerShell quote-escaping issues with `curl.exe`. Terminal alternative: `Invoke-RestMethod` with a PowerShell hashtable body (see Day 3 log).
