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

**Last completed:** Day 9 — Verified via direct SQL against the hosted Neon DB that all traces (10 total, spanning Day 3 through Day 8) have correct span structure (1 `retrieval` + 1 `llm_call` each, no orphans) and that all 7 broken-scenario traces carry intact, correctly-typed ground truth (`injected_failure`, `expected_correct_source`, `expected_correct_chunk_index`) in the retrieval span's `raw_data`
**Next up:** Day 10 — Feature Extraction Engine: extractor for retrieval metrics (avg/max/min similarity, chunk count)
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
- **Why the RAG test app lives in its own top-level folder, not inside `backend/`** — Section 5.1 marks the "AI Application Layer" as External to the platform; building it inside `backend/app/` would blur the exact boundary the platform exists to observe from the outside (Day 6)
- **Local embeddings vs. an embeddings API** — `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim, CPU, no API key) keeps the RAG test app's retrieval concern free and local; this is separate from Groq, which is used later purely for generation, not embedding (Day 6)
- **Paragraph-based chunking** — splitting on blank lines works well here because each policy document's paragraphs are already self-contained rules; avoids arbitrary character-count splits that could cut a key sentence in half (a failure mode deliberately *reintroduced* on purpose in Day 8) (Day 6)
- **Chunks stored in a separate `documents` table, not the platform's schema** — the platform never queries this table directly; it only ever sees the trace the RAG app sends it via the API, keeping the "platform doesn't own the pipeline" boundary honest even in V1, ahead of it mattering for real in Section 21 (Day 6)
- **venv activation is a silent failure mode, not just a convenience** — `pip install` without `(venv)` showing in the prompt installs into the user/global Python via `--user` fallback, not the venv; the package appears "installed" (pip says Successfully installed) but the script run under the venv's Python still can't see it. Always confirm `(venv)` is present before installing or running (Day 6)
- **pgvector's `<=>` operator is cosine *distance*, not similarity** — 0 means identical, 2 means opposite; converting via `1 - distance` gives the "higher = more similar" score used throughout the design doc's language (Day 7)
- **Cold model-load time vs. actual retrieval time** — `retrieve()`'s first call includes loading `SentenceTransformer` into memory, which dwarfs the actual pgvector query; something to isolate properly once real latency metrics matter (Feature Extraction, Days 10-12), not conflate as "slow retrieval" (Day 7)
- **LLM non-determinism at low but nonzero temperature** — identical code, identical query, two different Groq calls produced differently-worded (both correct) answers at `temperature=0.2`; matters for Day 8, since a "broken" trace needs to be broken by a deliberate config change, not confused with ordinary run-to-run variance (Day 7)
- **Why the RAG test app computes its own `total_cost_usd`** — Groq's free tier means actual spend is $0, but hardcoding published per-token pricing into the trace payload gives Feature Extraction (Day 12) and Evidence Producers realistic, non-zero cost data to reason about, matching what a real paid deployment would report (Day 7)
- **A "broken" trace needs a verified, specific breaking condition, not an assumed one** — the first candidate query for Low Top-K (the original Day 7 damage-related query) turned out to still answer correctly at `top_k=1`, because the retrieved chunk happened to duplicate the needed fact. Failure injection has to be probed and confirmed empirically (via a diagnostic script), the same way retrieval or reasoning correctness would be — assuming a query "should" break something isn't the same as verifying it does (Day 8)
- **Different failure mechanisms produce different failure *signatures*, not just "wrong answers"** — Low Top-K produced a confident "I don't have enough info" refusal; Bad Chunking produced a partially-correct-but-hedging answer (fact stated, process unclear); Bad Metadata Filter produced total blindness to the correct document. This distinction matters directly for Day 14+: an Evidence Producer inspecting retrieval will need different signals to tell "ranking excluded the right chunk" apart from "the right document was never a candidate" apart from "the right chunk existed but was semantically fragmented" (Day 8)
- **Metadata filtering happens *before* similarity search, not as part of it** — a wrong category filter (e.g., `category="warranty"` on a returns question) removes an entire document from the candidate pool up front; no amount of embedding quality or `top_k` tuning could recover the correct chunk, because it's excluded before cosine distance is even computed against it (Day 8)
- **Ground truth needs to be recorded on the trace itself, not just known during testing** — `injected_failure`, `expected_correct_source`, and `expected_correct_chunk_index` were added to the retrieval span's `raw_data` for all 3 broken scenarios; without this, a broken trace would just look like a regular (bad) trace by Day 14, with no recorded record of what the *correct* answer should have been (Day 8)

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
**Status:** ✅ Complete
**Design doc reference:** Section 17.2
**Learning objective (per design doc):** What chunking and embedding actually do mechanically

**What was built:**
- `rag-test-app/` — new top-level folder, sibling to `backend/` and `frontend/`, own venv, own `requirements.txt`, own `.env` (same `DATABASE_URL` as `backend/.env`), own `.gitignore` (`venv/`, `.env`, `__pycache__/`, `*.pyc`)
- `rag-test-app/documents/` — 3 sample company-policy `.txt` files with deliberately specific, unambiguous rules: `return_policy.txt` (includes the Product X non-returnable/safety-certification detail from Section 2's example scenario), `shipping_policy.txt`, `warranty_policy.txt`
- `rag-test-app/create_table.py` — creates `documents` table (`id`, `source_file`, `chunk_index`, `content`, `embedding VECTOR(384)`) in the same Neon Postgres instance used by the platform, via direct `psycopg2`
- `rag-test-app/ingest_documents.py` — paragraph-based chunker (splits on blank lines), embeds each chunk locally via `sentence-transformers` (`all-MiniLM-L6-v2`), truncates and re-inserts into `documents` on every run (idempotent for repeated testing)
- `rag-test-app/verify_ingestion.py` — sanity-check script: chunk count per file, total count, and a targeted lookup confirming the Product X chunk is intact and retrievable

**Verified:**
- `python create_table.py` → `documents table ready.`
- `python ingest_documents.py` → `return_policy.txt: 5 chunks`, `shipping_policy.txt: 5 chunks`, `warranty_policy.txt: 4 chunks`, `Done. Inserted 14 chunks total.`
- `python verify_ingestion.py` → confirmed same per-file counts, total of 14, and the Product X paragraph returned intact and unsplit

**Deviation logged:** none functionally — see Deviations section for the venv-activation troubleshooting note (Day 6).

---

### Day 7 — Wire retrieval + prompt + Groq LLM call; POST full trace
**Status:** ✅ Complete
**Design doc reference:** Section 17.2
**Learning objective (per design doc):** This is the AI Application Layer — why it must stay decoupled from the platform

**What was built:**
- Groq API key created (free tier), stored in `rag-test-app/.env` as `GROQ_API_KEY`; `groq` and `requests` packages installed
- `rag-test-app/retrieval.py` — `retrieve(query, top_k=3)`: embeds the query with the same local model used for ingestion, runs a pgvector cosine-similarity search (`<=>` operator, converted to a `1 - distance` similarity score) against `documents`, returns top-k chunks + retrieval latency
- `rag-test-app/generation.py` — `build_prompt()` assembles a system prompt (instructs the model to answer only from provided excerpts) + retrieved chunks + the user query; `generate()` calls Groq (`llama-3.3-70b-versatile`, `temperature=0.2`), returns the answer, full prompt text, token counts, and generation latency
- `rag-test-app/post_trace.py` — runs retrieval + generation, computes `total_latency_ms` and a realistic `total_cost_usd` (from Groq's published per-token pricing, even though actual free-tier spend is $0), packages everything into the exact `TraceCreate` shape from `backend/app/trace/schemas.py` (retrieval span + llm_call span, each with real `raw_data`), and POSTs to the live Render backend

**Verified:**
- `python retrieval.py` on the Section 2 example query ("Can I return Product X? It is within the 30-day return period.") correctly surfaced the Product X non-returnable chunk as the top match (similarity 0.615), ahead of the general returns and damaged-items chunks
- `python generation.py` produced a correct answer (Product X is non-returnable) with sane token counts (331 prompt / 83 completion)
- `python post_trace.py` → `Status: 201`, full trace object returned with server-generated `id`, both spans nested with complete `raw_data` (retrieval results, full prompt text, model config, answer, token counts) — confirmed live in production (Render → Postgres), not just locally

**Deviation logged:** none — see Learning Log for the cold-model-load-time and LLM-non-determinism notes to carry into later days.

---

### Day 8 — Deliberately broken scenarios (failure injection)
**Status:** ✅ Complete
**Design doc reference:** Section 17.2
**Learning objective (per design doc):** Failure injection as a testing discipline

**What was built:**
- `rag-test-app/probe_topk.py` — diagnostic script testing candidate queries against `retrieve()` at `top_k=5` to find a query where the correct chunk does not rank first; used again for later probing (Scenario 2 verification)
- `rag-test-app/post_trace_scenarios.py` — parameterized version of `post_trace.py`; `run_and_post()` now accepts `top_k`, `table`, `category`, and a `scenario` label, and tags every posted trace's retrieval span with `injected_failure`, `expected_correct_source`, `expected_correct_chunk_index` (flexible `raw_data` JSON, no schema migration needed — real production traces simply won't have these keys)
- **Scenario 1 — Low Top-K:** query `"I don't want Product X anymore, can I send it back for a refund?"` naturally ranks the correct chunk (Non-Returnable Categories, idx=2) at rank 2, behind a lexically-overlapping but inapplicable damage-exception chunk (idx=3). `top_k=1` truncates the correct chunk out entirely.
- **Scenario 2 — Bad Chunking:** `rag-test-app/create_table_bad_chunking.py` creates a second table `documents_bad_chunking` (same schema as `documents`); `rag-test-app/ingest_bad_chunking.py` re-chunks `return_policy.txt` using a fixed 120-character splitter (no sentence/paragraph awareness), shattering the Non-Returnable Categories paragraph into 4 disconnected fragments. `retrieve()` extended with a `table` parameter (defaults to `"documents"`, so all existing calls are unaffected).
- **Scenario 3 — Bad Metadata Filter:** `rag-test-app/add_category_column.py` adds a `category` column to the existing `documents` table, backfilled by source file (`return_policy.txt`→`returns`, `shipping_policy.txt`→`shipping`, `warranty_policy.txt`→`warranty`). `retrieve()` extended with an optional `category` parameter that adds a `WHERE category = %s` clause when set. Scenario deliberately passes `category="warranty"` for a plain returns question, excluding `return_policy.txt` from the candidate pool before similarity search runs.

**Verified (each scenario tested standalone before posting, then posted as a real trace — all `201`):**
- **Low Top-K:** retrieved chunk = only the damage-exception chunk (idx=3); model responded *"I'm unsure about the refund process... the standard return policy is not included in the excerpt"* — correctly recognized insufficient context rather than hallucinating, but still failed to answer the customer's actual question
- **Bad Chunking:** retrieved 3 fragments of the shattered Non-Returnable Categories paragraph; model responded *"Product X is excluded from standard returns... I'm unsure if it can be returned under warranty... doesn't provide clear instructions"* — got the core fact right but hedged on process, since the fragments were individually true but decontextualized
- **Bad Metadata Filter:** retrieved only `warranty_policy.txt` chunks (idx 2, 3, 0); model responded *"the provided excerpts only discuss warranty claims and do not mention a return policy"* — correct document was never a candidate, regardless of ranking quality
- All 3 scenario traces confirmed posted to production (`https://ai-engineering-copilot.onrender.com/api/v1/traces`) with `injected_failure` correctly recorded on each retrieval span

**Deviation logged:** none functionally — `category` addition was applied directly to the existing `documents` table (not a separate table) since it's a pure metadata addition that doesn't corrupt existing chunks/embeddings, unlike Scenario 2 which required an isolated table because the chunking itself was being corrupted.

### Day 9 — Buffer / catch-up
**Status:** ✅ Complete
**Design doc reference:** Section 17.2
**Learning objective (per design doc):** Buffer / catch-up day

**What was done:**
- Ran 3 verification queries directly against the hosted Neon DB (via Neon's SQL editor), independent of the API, to confirm Day 7–8 traces survived storage correctly rather than just trusting the `201` responses from ingestion
- Query 1: confirmed 10 traces total in `traces`, all `status = 'ingested'`, spanning Day 3 manual tests through Day 8's scenario posts
- Query 2: confirmed every trace_id has exactly one `retrieval` span and one `llm_call` span — no missing spans, no orphaned trace_ids, no duplicates
- Query 3: pulled `injected_failure` / `expected_correct_source` / `expected_correct_chunk_index` back out of the retrieval span's `raw_data` for all broken-scenario traces — all 3 failure types represented, all correctly reading back as `return_policy.txt` / chunk index `2`, no corruption or type mangling through the JSON round trip

**Findings:**
- 7 broken-scenario traces exist, not 3 (`low_top_k` ×4, `bad_chunking` ×2, `bad_metadata_filter` ×1) — `post_trace_scenarios.py` was run more than once, and each run appends new rows rather than overwriting. This is consistent with the existing "safe to re-run, idempotent POSTs" note (idempotent = won't crash/corrupt, not = won't create duplicates). No action needed now, but Day 22 (testing Reasoning against these) should either target one trace_id per failure type or expect multiple hits per category.
- No data-integrity issues found. Ground truth is trustworthy for Days 10+.

**Deviation logged:** `json ? 'key'` (existence operator) doesn't work on plain `json` columns — only `jsonb` supports the `?` operator, since it requires a parsed binary representation to check key existence, which `json` (text-stored) doesn't have. Fixed by casting: `raw_data::jsonb ? 'injected_failure'`. No schema change needed — `->>` (used elsewhere) works fine on `json` already; this only affects existence checks specifically.

**Verified:** All 10 traces structurally sound; all 7 ground-truth payloads intact and correctly typed. Day 9 verification passed — proceeding to Day 10 (Feature Extraction Engine) on trustworthy data.

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
- **venv activation troubleshooting (Day 6):** early in Day 6, `pip install` and `python create_table.py` were run without the venv actually active (`(venv)` prefix missing from prompt); pip silently fell back to a `--user` install into global Python, so `psycopg2`/`dotenv` appeared installed but weren't visible to the venv's interpreter. Resolved by explicitly running `venv\Scripts\activate` and reinstalling once `(venv)` was confirmed in the prompt. No lasting impact — logged as a reminder to visually confirm `(venv)` before installing/running on any future day.

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
- **RAG test app repo path:** `C:\Users\kirut\Desktop\AI Engineer Copilot\rag-test-app` — sibling folder to `backend/` and `frontend/`, own venv, own `.env` (same `DATABASE_URL` as backend), own `.gitignore`
- **Activate rag-test-app venv:** `venv\Scripts\activate` (from `rag-test-app/`) — **always confirm `(venv)` appears in the prompt before installing or running anything**; see Day 6 deviation note
- **Re-run ingestion:** `python ingest_documents.py` (from `rag-test-app/`, venv active) — safe to re-run any time, truncates and reinserts all chunks
- **Sanity-check ingestion:** `python verify_ingestion.py` — prints per-file chunk counts, total, and confirms the Product X chunk is intact
- **`documents` table:** lives in the same Neon `neondb` database as the platform's tables, but is only ever read by `rag-test-app`'s own retrieval step (Day 7+) — the platform never queries it directly, only receives traces via the API
- **`rag-test-app/.env` also needs `GROQ_API_KEY`** (free tier, from console.groq.com) alongside `DATABASE_URL`
- **Seed IDs for trace payloads:** `org_id = ab6ed8df-5f97-428c-8d70-77773c676988`, `application_id = a3c12e69-94bf-48a5-9183-293356c59d47` (from `backend/seed.py` output, Day 3) — hardcoded at the top of `rag-test-app/post_trace.py`
- **Run the full loop:** `python post_trace.py` (from `rag-test-app/`, venv active) — retrieves, calls Groq, packages a trace, POSTs to `https://ai-engineering-copilot.onrender.com/api/v1/traces`. First call after Render idles may take a few extra seconds (cold start), not a bug
- **`documents` table now has a `category` column** (`returns` / `shipping` / `warranty`, backfilled by source file, Day 8) — `retrieve()` accepts an optional `category` param that adds a `WHERE category = %s` filter when set; omit it for unfiltered search (unchanged default behavior)
- **`documents_bad_chunking` table (Day 8)** — isolated copy of `return_policy.txt` only, re-chunked via fixed 120-char splits instead of paragraphs; used only for Scenario 2, does not have a `category` column. `retrieve()` accepts a `table` param (defaults to `"documents"`) to target it.
- **Run Day 8 broken scenarios:** `python post_trace_scenarios.py` (from `rag-test-app/`, venv active) — posts all 3 injected-failure traces in sequence (low_top_k, bad_chunking, bad_metadata_filter); safe to re-run, all idempotent POSTs. Each trace's retrieval span carries `injected_failure`, `expected_correct_source`, `expected_correct_chunk_index` for later ground-truth comparison.
