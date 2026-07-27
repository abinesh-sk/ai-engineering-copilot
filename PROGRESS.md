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

**Last completed:** Day 3 — POST /api/v1/traces and GET /api/v1/traces/{id}, validated with real requests
**Next up:** Day 4 — Set up Redis (Upstash) and a minimal background worker that just logs receipt of a job
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

--- — Redis (Upstash) + minimal background worker
**Status:** ⬜ Not started

### Day 5 — Deploy backend + frontend skeleton
**Status:** ⬜ Not started

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

---

## Environment / Setup Notes

- **Repo path:** `C:\Users\kirut\desktop\ai-engineering-copilot\backend`
- **Activate venv:** `venv\Scripts\activate` (from `backend/`)
- **Run server:** `uvicorn app.main:app --reload` (from `backend/`, venv active)
- **Local URLs:** `http://127.0.0.1:8000` (root), `/health`, `/docs` (interactive API explorer), `/db-check` (temp)
- **DB:** Neon project `ai-engineering-copilot`, database `neondb`, pgvector enabled
- **Env vars required:** `DATABASE_URL` in `backend/.env` (not committed — see `.gitignore`)
- **Not yet deployed** — local dev only through Day 1
- **Seed data:** `python seed.py` (from `backend/`) creates one Organization + one Application, prints their UUIDs — needed for any trace POST test. Re-run only if the DB is reset.
- **Testing endpoints on Windows:** use `http://127.0.0.1:8000/docs` (Swagger UI) — avoids PowerShell quote-escaping issues with `curl.exe`. Terminal alternative: `Invoke-RestMethod` with a PowerShell hashtable body (see Day 3 log).
