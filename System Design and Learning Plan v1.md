# AI Engineering Copilot — Complete Project Reference

> **Purpose of this document:** This is the single source of truth for the AI Engineering Copilot project. It captures the original vision, every architectural decision made, every modification from the original spec, the reasoning behind each tradeoff, and the full 30-day implementation plan. Open this in a new chat to continue implementation without losing context.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [What Makes This Different From Existing Tools](#3-what-makes-this-different-from-existing-tools)
4. [Design Principles](#4-design-principles)
5. [Final Architecture](#5-final-architecture)
6. [Key Architectural Decisions & Tradeoffs](#6-key-architectural-decisions--tradeoffs)
7. [System Modules — Detailed Design](#7-system-modules--detailed-design)
8. [LLM Usage — Where, Why, and the No-LLM Alternative](#8-llm-usage--where-why-and-the-no-llm-alternative)
9. [Database Schema (V1)](#9-database-schema-v1)
10. [API Design](#10-api-design)
11. [Deployment Topology](#11-deployment-topology)
12. [Folder Structure](#12-folder-structure)
13. [Frontend Pages](#13-frontend-pages)
14. [Security](#14-security)
15. [What Is Deferred to V2](#15-what-is-deferred-to-v2)
16. [30-Day Implementation Plan](#16-30-day-implementation-plan)
17. [How to Use This Document in a New Chat](#17-how-to-use-this-document-in-a-new-chat)

---

## 1. Project Overview

**AI Engineering Copilot** is an internal-style engineering platform that watches an AI application's executions, automatically diagnoses why a bad answer happened, backs every diagnosis with evidence, remembers past incidents, and lets an engineer safely test a fix before trusting it in production.

This is **not** an observability dashboard. Tools like LangSmith, LangFuse, and Arize Phoenix answer *"what happened"* — they visualize traces, spans, and metrics. This platform answers the harder question: **"why did it fail, and what fixes it."**

### Project constraints (non-negotiable)
- **Zero cost** — no paid APIs, no paid hosting, no paid services
- **Hosted website** — deployed publicly, not running locally
- **~2 hours/day** for 30 days — personal project, not a startup
- **Learn by building** — understanding every layer is as important as shipping

---

## 2. Problem Statement

Modern AI systems fail in ways that are expensive to debug manually.

**Example:** A customer support chatbot is asked:
> "Can I return Product X? It is within the 30-day return period."

The chatbot replies: **"Yes."**

The actual company policy: Product X is in the **Non-Returnable** category.

To find out why, an engineer must manually inspect:
- Retrieval results, embeddings, similarity scores
- Retrieved chunks and metadata filters
- The constructed prompt and system prompt
- LLM configuration and generated output
- Memory access, tool calls, agent routing decisions
- Latency, cost, errors, warnings

Eventually they discover: **the correct refund policy document was never retrieved.**

This investigation takes minutes to hours for one conversation. At 10,000 or 1,000,000 conversations, manual debugging is impossible.

### Where existing tools fall short

| Tool | Category | What it does | What it misses |
|---|---|---|---|
| LangSmith | Observability | Trace/span visualization, token tracking | Root cause, recommendations |
| LangFuse | Observability | Metrics, latency, cost dashboards | Why it failed |
| Arize Phoenix | Observability | Evaluation scoring, drift detection | Historical memory, replay |
| Helicone | Observability | Request logging, cost tracking | Diagnosis |
| W&B Weave | Evaluation | Offline batch evaluation | Production diagnosis |
| RAGAS / DeepEval | Evaluation | Groundedness, faithfulness scoring | Per-incident root cause |

**The gap:** existing tools tell you *what happened*. None of them tell you *why*, remember that it happened before, or let you test a fix safely before applying it.

---

## 3. What Makes This Different From Existing Tools

### Real differences (genuinely novel):

**1. Evidence Producer pattern** — instead of one monolithic evaluator or a flat log, independent per-component modules each report their own health. When retrieval AND the LLM both look suspicious, you get ranked evidence from two independent sources — much more defensible than a single score.

**2. Historical incident memory** — every diagnosed incident is stored as a vector embedding. When a new failure arrives, the system finds similar past incidents and surfaces what fixed them previously. No current AI observability tool does this. It is closer to what PagerDuty does for infrastructure (grouping alerts by similarity, surfacing runbooks) than what any LLM tool currently offers.

**3. Replay engine** — take a specific failed production execution, change one config value (Top-K, chunk size, embedding model, temperature), re-run it in a sandbox, and get a full before/after comparison with an explanation of why the result changed. LangSmith has "experiments" but they run against curated offline datasets, not specific production failures with config modification.

### Honest positioning:
This platform sits **alongside** LangSmith (which handles observability/logging), not **instead** of it. The realistic production story is: LangSmith captures your traces → AI Engineering Copilot consumes them and adds the diagnosis + replay layer on top. That is a stronger product story than "another observability dashboard."

---

## 4. Design Principles

These are non-negotiable constraints, not aspirations. Every architectural decision below traces back to at least one of these.

| # | Principle | Meaning |
|---|---|---|
| 1 | **Reliable** | Every diagnosis must be backed by evidence. Never rely solely on LLM reasoning. |
| 2 | **Explainable** | Every recommendation must explain *why* it was generated, in terms an engineer can verify. |
| 3 | **Lightweight** | Avoid unnecessary LLM calls. Perform deterministic processing wherever possible. One LLM call in the entire pipeline. |
| 4 | **Extensible** | Adding a new evidence producer, retriever, LLM provider, or vector store requires minimal code changes. |
| 5 | **Vendor independent** | No hard dependency on any single LLM provider, vector DB, or framework. All external dependencies hidden behind interfaces. |

---

## 5. Final Architecture

### Pipeline (linear, one-directional)

```
AI Application (local RAG script — your test subject)
        │
        │  POST /api/v1/traces
        ▼
┌─────────────────────────────────────────────┐
│          BACKEND  (FastAPI on Render/Fly)    │
│                                             │
│  API Layer                                  │
│   └─ validates, stores trace, enqueues job  │
│   └─ returns 202 immediately                │
│                                             │
│  Redis Queue (Upstash)                      │
│   └─ decouples ingestion from processing    │
│                                             │
│  Background Worker (same container)         │
│   ├─ Feature Extraction      ← deterministic│
│   ├─ Evidence Producers      ← deterministic│
│   ├─ Historical Search       ← deterministic│
│   ├─ Root Cause Reasoning    ← ONE LLM call │
│   └─ Recommendation scoring  ← deterministic│
│                                             │
└─────────────────────────────────────────────┘
        │
        ▼
PostgreSQL + pgvector (Neon/Supabase free tier)
        │
        ▲  reads via API
        │
React Frontend (Vercel)
```

### The two-color rule
- **Green stages** (Feature Extraction, Evidence Generation, Historical Search, Recommendation scoring) — fully deterministic, no AI, no cost
- **Pink stage** (Root Cause Reasoning) — the one LLM call, happens only after all green stages have already narrowed the problem

---

## 6. Key Architectural Decisions & Tradeoffs

Every decision below is deliberate. Each one is explained so you can defend it in an interview.

### Decision 1 — Modular monolith, not microservices

**Original spec:** 6 independent microservices (Trace, Evidence, Reasoning, Replay, Historical Learning, Analytics)

**What we build:** Single deployable FastAPI backend, internally split into 6 clean module folders

**Why:** Microservices earn their cost when different services need independent scaling, different teams own them, or independent deployment matters. None of those conditions apply here. Six services means 6x deployment overhead, 6x logging, 6x network boundary debugging, with no benefit at one-user scale.

**The key insight:** This is not a simplification. Shopify and early Stripe ran as modular monoliths. The module seams are clean enough that any single module (e.g., Reasoning if LLM load grew) could be extracted into its own service later without a rewrite.

**The one rule that keeps this honest:** Data flows one direction only. `evidence/` can import from `features/`, but `features/` must never import from `evidence/`. Catching a backwards import is the signal a boundary is leaking.

---

### Decision 2 — Synchronous ingestion, asynchronous processing

**Why this matters:** Ingestion must be fast and must never fail because a downstream stage is slow. The LLM call might take 3-5 seconds. You do not want trace ingestion to block on that.

**Pattern:**
1. API receives trace → validates → writes to Postgres → pushes job ID to Redis → returns `202 Accepted` (all under ~100ms)
2. Background worker picks up job → runs Feature Extraction → Evidence → Historical Search → Reasoning → writes results to DB

**What we use instead of Kafka:** Redis via Upstash free tier (using `arq` Python library for the worker). The interface is identical to what you'd swap in Kafka/SQS for later — "enqueue a job, a worker picks it up." You learn the real pattern without the operational cost of running Kafka.

---

### Decision 3 — pgvector instead of Qdrant

**Original spec:** Dedicated Qdrant vector database

**What we build:** pgvector extension inside the same Postgres instance

**Why:** At personal project scale (thousands of vectors, not millions), pgvector's performance is identical to Qdrant for our use case. This eliminates an entire hosted service from the infrastructure. Code is written against a `VectorStore` interface, so swapping to real Qdrant later is a config change, not a rewrite.

---

### Decision 4 — Groq free tier instead of OpenAI/Anthropic

**Why:** Zero cost constraint. Groq provides fast hosted inference on open models (Llama 3.3 70B) for free within daily rate limits.

**How it stays vendor-independent:** The Reasoning Engine calls a `LLMProvider` interface. `GroqProvider` is the default implementation. `AnthropicProvider`, `OpenAIProvider`, `OllamaProvider` can all be added behind the same interface. Switching is a config value, not a code change.

---

### Decision 5 — Schema-level multi-tenancy even for one user

**What we do:** Every table has an `org_id` column. Every query filters by it. Only one org record exists in practice.

**Why:** Retrofitting multi-tenancy onto a schema that was never designed for it is one of the most painful migrations a growing team can face. Adding `org_id` everywhere now costs nothing. The migration it prevents could cost weeks.

---

### Decision 6 — LLM is optional for root cause ranking

The LLM currently produces:
- The plain-language causal explanation (hard to replace)
- Root cause ranking (can be replaced with a weighted scoring function)
- Recommendations (can be replaced with a lookup table)

**The system works without an LLM** for diagnosis and recommendations — it just loses the human-readable narrative explanation. This is a product decision, not an architectural constraint. V1 includes the LLM call for richer output, but the deterministic fallback is documented and implementable.

---

### Decision 7 — Hosted website, not local

**Frontend:** React + TypeScript on **Vercel** (ideal for static/SSR, generous free tier)

**Backend:** FastAPI on **Render** or **Fly.io** (real long-running container — needed for the background worker; Vercel serverless functions cannot run persistent workers)

**Why not everything on Vercel:** Vercel serverless functions die after the request. A background worker needs to stay alive to poll the queue. This is the reason the backend is on Render/Fly specifically.

**Cold start tradeoff:** Free tier containers on Render/Fly sleep after ~15 min idle and take a few seconds to wake. Explicitly accepted as a tradeoff for $0/month cost.

---

## 7. System Modules — Detailed Design

### Module 1 — Trace Collection & Storage

Every AI application execution is packaged into a structured trace and POSTed to `/api/v1/traces`.

**What a trace contains:**
- User query, conversation ID, session ID, timestamp
- Retriever results: chunk IDs, similarity scores, chunk metadata, document version
- Prompt: system prompt, user prompt, assembled context
- LLM config: model, temperature, top-p, max tokens
- Generated answer
- Latency, token usage, cost
- Tool calls, memory accesses, agent decisions
- Errors, warnings, environment info

**Ingestion is fast by design:** validate → write `Traces` + `TraceSpans` rows → enqueue job → return 202. Nothing slow happens inside the request.

---

### Module 2 — Feature Extraction Engine

**What it does:** Turns messy nested trace JSON into flat, queryable numbers.

**Why it exists as a separate stage:** Every downstream stage (evidence producers, reasoning engine, replay comparison) needs to compare numbers, not parse raw JSON. This translation layer is written once and reused everywhere.

**Metrics extracted:**
- `avg_similarity`, `max_similarity`, `min_similarity`
- `retriever_recall` (did the expected document appear in results?)
- `prompt_length`, `context_tokens`, `completion_tokens`
- `latency_ms`, `cost_usd`
- `groundedness_score` (deterministic: do answer claims appear in retrieved context?)
- `citation_coverage` (how many answer claims cite a source?)
- `chunk_count`, `chunk_distribution`

All written to the `Metrics` table as key/value rows.

---

### Module 3 — Evidence Generation Engine

**The most important architectural decision in the system.**

**What it is NOT:** a pile of hundreds of if/else rules trying to jump from raw symptoms to a final diagnosis.

**What it IS:** independent per-component modules (Evidence Producers), each of which:
1. Receives only the metrics relevant to its own area
2. Applies a narrow, local check
3. Emits a standardized observation: `{component, severity (0-1), evidence_text}`
4. **Never claims to know the overall root cause**

**Evidence Producers (V1):**

| Producer | What it checks |
|---|---|
| `RetrieverEvidenceProducer` | avg similarity vs historical baseline, whether expected doc is in results |
| `PromptEvidenceProducer` | prompt length anomalies, missing expected context sections |
| `LLMEvidenceProducer` | deterministic groundedness check — do answer claims appear in retrieved context? |
| `MemoryEvidenceProducer` | memory hit rate, inconsistencies (stub in V1, full in V2) |
| `ToolEvidenceProducer` | tool call success rate, unexpected failures (stub in V1) |

**Why this is better than a monolithic rule engine:**
- Adding a new producer is a pure addition — one new file, no existing code touched
- Each producer is independently testable
- Diagnosis is deferred to the Reasoning Engine which can weigh all observations together — the way a senior engineer synthesizes multiple signals rather than trusting the first alarming number

**Output example:**
```
{component: "retriever",  severity: 0.91, evidence_text: "Average similarity 0.22, significantly below historical baseline of 0.68"}
{component: "prompt",     severity: 0.12, evidence_text: "Prompt length within expected range"}
{component: "llm_output", severity: 0.78, evidence_text: "Answer claims not grounded in retrieved context"}
```

---

### Module 4 — Historical Incident Learning Engine

**What it is:** organizational memory for AI failures — conceptually identical to RAG, but retrieving engineering knowledge instead of documents.

**How it works:**
1. Every diagnosed incident is stored: root cause, fix applied, whether fix worked, evidence summary, vector embedding
2. When a new trace arrives, its evidence is embedded and searched against stored incidents using pgvector cosine similarity
3. If a match is found (e.g., 97% similar), its previous root cause and fix become strong signals for the Reasoning Engine

**Cold start:** manually seed 2-3 historical incidents on Day 20 so the search has something to match against from day one.

**Why no existing tool does this:** most observability platforms treat every execution as independent. This platform builds memory that compounds over time — every incident diagnosed makes future diagnoses faster and more confident.

---

### Module 5 — Root Cause Reasoning Engine

**This is the one place an LLM is called.**

**What the LLM receives:**
```
Evidence list (from Module 3):
  - retriever: severity 0.91, "similarity unusually low, correct doc missing"
  - prompt: severity 0.12, "normal"
  - llm_output: severity 0.78, "answer not grounded in context"

Historical match (from Module 4):
  - 97% similar to incident #312
  - Previous root cause: Retriever failure (metadata filter excluding correct doc)
  - Previous fix: Increase Top-K from 5→10, enable hybrid search
  - Fix was successful
```

**What the LLM is NOT given:** the raw trace. Never. Raw traces are messy and expensive to reason over.

**What the LLM produces (structured JSON output):**
```json
{
  "root_cause": "Retriever failure — correct document excluded by metadata filter",
  "confidence": 0.91,
  "ranked_causes": [
    {"component": "retriever", "probability": 0.94},
    {"component": "prompt",    "probability": 0.31},
    {"component": "llm",       "probability": 0.14}
  ],
  "explanation": "The LLM produced an ungrounded answer because the prompt lacked the refund policy. The prompt lacked it because the retriever failed to surface the correct document. The retriever failed because...",
  "recommendations": [
    {"action": "Increase Top-K from 5 to 10", "reason": "...", "confidence": 0.91, "tradeoff": "slight latency increase"}
  ]
}
```

**Why this is reliable:** the LLM is doing a narrow, well-defined task (synthesize a short structured evidence list into a diagnosis) not open-ended reasoning over messy data. Small models are much more reliable at constrained tasks.

---

### Module 6 — Replay Engine

**The flagship feature.**

An engineer opens a failed execution, changes any config value, and re-runs it in an isolated sandbox. Production data is never touched.

**Modifiable parameters:**
- `top_k`, `chunk_size`, `chunk_overlap`
- `embedding_model`, `retriever_type`
- `temperature`, `top_p`, `max_tokens`
- `metadata_filters`, `hybrid_search` (on/off)
- `system_prompt`, `knowledge_base_version`
- `reranker` (on/off), `llm_model`

**What a replay produces:**
- New trace + spans (written to `ReplayExecutions`, never to `Traces`)
- New metrics from Feature Extraction (same code path, different data)
- New evidence from Evidence Producers (same code path)
- Side-by-side comparison stored in `ReplayComparisons`
- Plain-language explanation of *why* the result changed (reuses the Reasoning Engine)

**Example comparison:**

| Metric | Original | Replay |
|---|---|---|
| avg_similarity | 0.24 | 0.86 |
| Documents retrieved | Shipping Policy, Warranty, FAQ | **Refund Policy**, Shipping Policy, FAQ |
| groundedness | 0.52 | 0.94 |
| hallucination_risk | High | Very Low |
| latency_ms | 310 | 356 |
| cost_usd | $0.0018 | $0.0020 |

**Why this is only buildable in Phase 6:** replay reuses Feature Extraction, Evidence Producers, and Reasoning — it's only buildable once those modules exist and work correctly.

---

## 8. LLM Usage — Where, Why, and the No-LLM Alternative

### Where the LLM is used

**Exactly two places, both in the same module:**

1. **Root Cause Reasoning** (Phase 5, Day 21) — one call per trace analysis
2. **Replay Explanation** (Phase 6, Day 26) — one call per replay, reusing the same Reasoning Engine

**Everything else is deterministic:** ingestion, feature extraction, evidence producers, historical search, replay execution, frontend.

### Why the LLM only here

The system does all the work that can be done deterministically *before* the LLM sees anything. By the time the LLM is called, the problem has already been narrowed to a short structured evidence list. The LLM's job is narrow and well-defined — synthesize this into a human-readable diagnosis. This is the task LLMs are good at. Open-ended reasoning over raw messy trace data is the task they are unreliable at.

### Can this be done without an LLM?

**Yes, mostly.** Here's what you'd replace:

| LLM task | Deterministic replacement |
|---|---|
| Root cause ranking | Weighted scoring: `score = severity × component_weight`, sort descending |
| Recommendations | Lookup table: `if retriever_failure and low_similarity → recommend("Increase Top-K")` |
| Plain-language explanation | **Cannot be replaced cleanly** — template outputs become too generic or too brittle |

A fully LLM-free version would still ingest traces, extract metrics, produce evidence, search historical incidents, replay executions, and compare results. It would lose the readable causal narrative. That's a real but acceptable tradeoff. The architecture supports both modes — the LLM call is one module, not woven throughout the system.

---

## 9. Database Schema (V1)

**Single Postgres instance with pgvector extension.**

Tables deliberately cut from the full spec (deferred to V2 or folded into existing tables): `KnowledgeBaseVersions`, `ReplayConfigurations` (separate), `IncidentEmbeddingsMetadata` (folded into `HistoricalIncidents`), full `Projects` table (collapsed to `org_id` column).

```sql
-- Identity & multi-tenancy (schema-ready even though only one org exists)
Organizations   (id, name, created_at)
Users           (id, org_id, email, hashed_password, role, created_at)
Applications    (id, org_id, name, framework_tag, created_at)

-- Raw trace data
Traces          (id, application_id, conversation_id, session_id,
                 user_query, generated_answer, llm_config jsonb,
                 latency_ms, cost_usd, environment, created_at)

TraceSpans      (id, trace_id, span_type, payload jsonb,
                 started_at, ended_at)
                -- span_type: 'retrieval' | 'prompt' | 'llm_call'
                --            | 'tool_call' | 'memory' | 'agent_decision'

-- Processed data (written by background worker)
Metrics         (id, trace_id, key, value, created_at)
                -- e.g. ('avg_similarity', 0.24), ('latency_ms', 310)

Evidence        (id, trace_id, component, severity, evidence_text, created_at)
                -- one row per producer per trace

-- AI outputs
RootCauseReports (id, trace_id, root_cause, confidence,
                  ranked_causes jsonb, explanation, created_at)

Recommendations  (id, report_id, action, reason, expected_improvement,
                  confidence, tradeoffs, estimated_cost, created_at)

-- Historical memory
HistoricalIncidents (id, trace_id, root_cause, confidence,
                     fix_applied, config_before jsonb, config_after jsonb,
                     fix_successful bool,
                     embedding vector(1536),  -- pgvector column
                     created_at)

-- Replay
ReplayExecutions  (id, original_trace_id, modified_config jsonb,
                   replay_answer text, replay_metrics jsonb,
                   status, created_at)

ReplayComparisons (id, replay_execution_id, diff jsonb,
                   explanation text, created_at)
```

**Why `org_id` everywhere matters:** every query in the codebase filters by `org_id` from day one. Adding multi-tenancy later without this in the schema requires a migration of every table and every query simultaneously — one of the more painful operations an engineering team can face.

---

## 10. API Design

Each endpoint corresponds directly to a pipeline stage. The API surface is intentionally small and mirrors the system's data flow.

| Method | Endpoint | Purpose | Notes |
|---|---|---|---|
| POST | `/api/v1/traces` | Upload execution trace | Returns 202, enqueues worker job |
| GET | `/api/v1/traces/{id}` | Get trace + spans + diagnosis status | Includes `status: processing|ready` |
| GET | `/api/v1/traces` | List traces with filtering | Pagination, filter by date/app/status |
| POST | `/api/v1/evidence/generate` | Trigger evidence generation | Internal/manual use |
| POST | `/api/v1/reasoning/analyze` | Generate root cause report | Calls LLM |
| POST | `/api/v1/replay` | Replay execution with modified config | Returns replay job ID |
| GET | `/api/v1/replay/{id}` | Get replay results + comparison | Includes diff and explanation |
| GET | `/api/v1/incidents/similar` | Find similar historical incidents | pgvector similarity search |
| POST | `/api/v1/recommendations` | Generate recommendations | Based on root cause report |
| GET | `/api/v1/dashboard` | Aggregate analytics | Most common failures, trends |
| POST | `/api/v1/auth/login` | Get JWT token | Returns access token |

---

## 11. Deployment Topology

**Total cost: $0/month**

| Layer | Service | Why this choice |
|---|---|---|
| Frontend | React + TypeScript → **Vercel** | Ideal for static/SSR, generous free tier |
| Backend API + Worker | FastAPI → **Render** or **Fly.io** free tier | Real long-running container; needed for background worker (Vercel serverless can't do this) |
| Database | PostgreSQL + pgvector → **Neon** or **Supabase** free tier | pgvector support built-in, several GB free |
| Queue | Redis → **Upstash** free tier | Thousands of commands/day free; works with `arq` Python library |
| LLM | **Groq** free tier (Llama 3.3 70B) | Fast, free, strong open model; behind interface so swappable |
| Trace-generating app | Local Python script | Calls the hosted API; no hosting needed |

**Known tradeoff:** Render/Fly free tier containers sleep after ~15 min idle. First request after idle takes a few seconds to wake. Explicitly accepted.

**Why the backend is NOT on Vercel:** Vercel functions are serverless — they die after the request. A Redis-backed background worker needs a persistent process. This is the one technical reason the backend must be on Render/Fly specifically.

---

## 12. Folder Structure

```
backend/
├── api/                    # FastAPI routes — thin, no business logic
│   ├── traces.py
│   ├── evidence.py
│   ├── reasoning.py
│   ├── replay.py
│   ├── incidents.py
│   ├── recommendations.py
│   ├── dashboard.py
│   └── auth.py
│
├── modules/
│   ├── trace/              # ingest, store, retrieve traces
│   │   ├── __init__.py
│   │   ├── service.py      # public interface
│   │   ├── models.py
│   │   └── schemas.py
│   ├── features/           # raw trace → structured metrics
│   │   ├── service.py
│   │   └── extractors.py
│   ├── evidence/           # evidence producers
│   │   ├── service.py
│   │   ├── base.py         # abstract EvidenceProducer interface
│   │   ├── retriever.py
│   │   ├── prompt.py
│   │   ├── llm_output.py
│   │   ├── memory.py       # stub in V1
│   │   └── tool.py         # stub in V1
│   ├── historical/         # incident storage + similarity search
│   │   ├── service.py
│   │   └── embeddings.py
│   ├── reasoning/          # the one LLM call
│   │   ├── service.py
│   │   └── prompts.py
│   ├── replay/             # sandbox re-execution + comparison
│   │   ├── service.py
│   │   └── executor.py
│   └── analytics/          # aggregate stats
│       └── service.py
│
├── core/
│   ├── llm_provider.py     # LLMProvider interface + GroqProvider impl
│   ├── vector_store.py     # VectorStore interface + PgVectorStore impl
│   ├── queue.py            # job enqueue/dequeue over Redis
│   └── auth.py             # JWT helpers
│
├── db/
│   ├── models.py           # SQLAlchemy ORM models
│   ├── session.py          # DB connection + session
│   └── migrations/         # Alembic migrations
│
├── worker.py               # background worker entrypoint
├── main.py                 # FastAPI app entrypoint
└── config.py               # env vars, settings

frontend/
├── src/
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── TraceExplorer.tsx
│   │   ├── TraceDetail.tsx
│   │   ├── Replay.tsx
│   │   ├── HistoricalIncidents.tsx
│   │   └── Analytics.tsx
│   ├── components/
│   └── api/                # typed API client
└── ...

rag_test_app/               # local script, not deployed
├── documents/              # fake company policy docs
│   ├── refund_policy.txt
│   ├── shipping_policy.txt
│   └── warranty.txt
├── rag_pipeline.py         # chunking, embedding, retrieval, LLM call
├── trace_sender.py         # packages and POSTs trace to backend
└── scenarios.py            # broken scenarios for testing
```

**The one-direction rule:** modules can import from modules to their left in the pipeline. `evidence/` can import `features/`. `reasoning/` can import `historical/` and `evidence/`. `features/` must never import `evidence/`. Backwards imports are the signal a boundary is leaking.

---

## 13. Frontend Pages

### Dashboard
- Total traces, failure rate, most common failure categories (bar chart)
- Average latency, cost trends (line charts)
- Replay success rate
- Recent incidents (table)

### Trace Explorer
- List of all traces, filterable by date / application / status (healthy/anomalous)
- Click a trace → Trace Detail

### Trace Detail
- Timeline of spans (retrieval, prompt assembly, LLM call, tool calls)
- Retrieved documents + similarity scores
- Assembled prompt (expandable)
- Generated answer
- Evidence section: one card per producer, showing severity + evidence text
- Root cause report: ranked failure probabilities, explanation, recommendations
- "Replay" button → opens Replay page pre-loaded with this trace

### Replay Page
- Split screen: Original (left) | Replay (right)
- Config editor: modify any parameter (Top-K, chunk size, temperature, system prompt, etc.)
- Side-by-side comparison table: retrieved docs, similarity scores, groundedness, latency, cost
- Explanation section: why the result changed
- "Save as historical incident" button

### Historical Incidents
- Searchable list of all past diagnosed incidents
- Per-incident: root cause, fix applied, fix successful (Y/N), similar incidents

### Analytics
- Most common failure categories over time
- Retriever performance trends
- Hallucination / groundedness trends
- Cost and latency distributions
- Replay success rate over time

---

## 14. Security

| Concern | V1 approach |
|---|---|
| Authentication | Self-rolled JWT (access token, 24h expiry) |
| Authorization | Single user/org in V1; schema-ready for RBAC later (`role` column on Users) |
| Multi-tenancy | `org_id` on every table, filtered in every query |
| Replay isolation | Replays write ONLY to `ReplayExecutions`/`ReplayComparisons` — never to `Traces` |
| Secrets | Environment variables only, never in code or committed to git |
| API keys | Groq key in env var, accessed via config module, never hardcoded |

---

## 15. What Is Deferred to V2

These are not rejected — they are explicitly deferred because building them before V1's pipeline produces real evidence data means designing against a problem that doesn't exist yet.

| Feature | Why deferred |
|---|---|
| **Evidence Graph** (causal graph with traversal) | Needs real evidence data from V1 first; flat evidence list ships in V1 |
| **Automated Replay Experiments** (multi-config search, auto-ranking) | Single manual replay must work before automating it |
| **Learning from Replay** (replay results feed back into historical memory) | Needs successful replays first |
| **Full trend analytics** | Needs historical data accumulation to be meaningful |
| **Prompt drift / embedding drift detection** | Needs baseline data from V1 |
| **CI/CD, GitHub, Jira, Slack integrations** | Post-V1 |
| **Qdrant** (separate vector DB) | pgvector is sufficient at V1 scale; interface makes swap easy |
| **Multiple LLM comparison** | Single LLM call works first |
| **Knowledge Graph visualization** | Evidence graph traversal (V2) needed first |
| **RBAC / full multi-user auth** | Schema ready; implementation deferred |

---

## 16. 30-Day Implementation Plan

### Ground rules
- ~2 hours/day, 30 days
- Each phase ends with **something runnable**, not just code written
- If a day runs long, roll it forward — don't skip it
- Days are a guide, not a contract
- When starting a session, say **"Day N"** to the assistant and you'll get that session's concrete tasks, code, and explanations

---

### Phase 1 — Foundation & Deploy Skeleton (Days 1–5)

**Goal:** Get an empty system fully wired and deployed before any real logic exists. Every later day becomes "add a feature," never "fight infrastructure."

| Day | Focus | You will learn |
|---|---|---|
| 1 | Repo structure (`backend/modules/...` layout), Python env, FastAPI hello-world, Postgres connection via Neon/Supabase | Why folder structure by domain instead of by technical layer |
| 2 | SQLAlchemy models for `Organizations`, `Users`, `Applications`, `Traces`, `TraceSpans`; first Alembic migration | Migrations as source of truth for schema, not "the DB just has stuff in it" |
| 3 | Build `POST /api/v1/traces` + `GET /api/v1/traces/{id}` for real; Pydantic validation; test with curl | What makes an API payload schema good for a system that must evolve |
| 4 | Set up Upstash Redis + `arq` background worker that logs "received job X" when a trace arrives | Decoupling ingestion from processing; producer/consumer pattern |
| 5 | Deploy backend to Render/Fly; push skeleton React app to Vercel calling a stubbed `/dashboard` endpoint | Deployment topology; why frontend and backend deploy independently; CORS |

**End state:** A trace POSTed from anywhere lands in real hosted Postgres, triggers a (currently empty) background job, and a live URL shows everything is connected. Nothing smart yet — nothing left to "set up" for the rest of the month.

---

### Phase 2 — Real Traces Flowing (Days 6–9)

**Goal:** Get real, intentionally-broken traces into your production database so every later module has ground-truth data to validate against.

| Day | Focus | You will learn |
|---|---|---|
| 6 | Local RAG script: load 3 fake company-policy docs (refund, shipping, warranty), chunk them, embed them, store in pgvector | What chunking and embedding actually do mechanically |
| 7 | Wire retrieval + prompt + Groq LLM call into the script; package the full execution into a trace payload and POST it to your deployed API | This *is* the AI Application Layer — why it must stay decoupled from the platform |
| 8 | Build 3 deliberately broken scenarios: (a) metadata filter excludes correct doc, (b) top-k=2 so correct doc never appears, (c) chunk splits a key sentence across two chunks | Failure injection as a testing discipline — you need known failures to validate diagnoses |
| 9 | Run all scenarios, confirm traces + spans land in hosted DB, inspect via direct SQL | Buffer/catch-up day |

**End state:** Real, varied, intentionally-broken traces sitting in your production database with known ground truth. You know exactly which trace is broken and why — so when the evidence engine catches it later, you can verify it's correct.

---

### Phase 3 — Feature Extraction Engine (Days 10–13)

**Goal:** Replace the background worker's "log and do nothing" stub with real metric extraction. Every trace automatically gets a `Metrics` row the moment it's ingested.

| Day | Focus | You will learn |
|---|---|---|
| 10 | `Metrics` table; extractor for retrieval metrics: `avg_similarity`, `max_similarity`, `min_similarity`, `chunk_count`, `retriever_recall` | Turning nested JSON into flat, queryable numbers — the translation layer everything else depends on |
| 11 | Prompt/context metrics: `prompt_length`, `context_tokens`, `completion_tokens` | Token counting, why it matters for cost and context-fit |
| 12 | Latency/cost metrics; wire all extractors into the background worker so they run automatically after ingestion | Pipeline composition — one worker, multiple stages, clean handoff |
| 13 | Query the `Metrics` table for your Day 8 broken scenarios — confirm `avg_similarity` is low where it should be | Buffer/catch-up day |

**End state:** Every trace automatically gets a clean, queryable metrics row. The broken scenarios show measurably wrong numbers — low similarity, suspicious context coverage.

---

### Phase 4 — Evidence Producers (Days 14–18)

**Goal:** Build the "independent observers" layer. Each producer runs independently, produces its own observation, and never claims the final root cause.

| Day | Focus | You will learn |
|---|---|---|
| 14 | `Evidence` table; `EvidenceProducer` abstract base class; `RetrieverEvidenceProducer` (is avg_similarity below baseline? is expected doc missing?) | Designing a plugin interface so adding producer #6 later is a 20-line file, not a refactor |
| 15 | `PromptEvidenceProducer` (prompt length anomalies; is expected context section present?) | Statistical baselines — what counts as "abnormal" without hardcoding magic numbers |
| 16 | `LLMEvidenceProducer` — deterministic groundedness check: do answer claims appear in retrieved context? (pure string/NLP check, no LLM) | Building a faithful faithfulness check without calling an LLM — a genuinely interesting NLP problem |
| 17 | Wire all three producers into the background worker; confirm evidence rows appear for each broken scenario | Validating the plugin pattern end-to-end — does the retriever producer correctly flag the broken-retrieval trace? |
| 18 | Buffer/catch-up; add `MemoryEvidenceProducer` and `ToolEvidenceProducer` as stubs (severity=0.0, "no anomaly detected") | Establishing the extension pattern without over-investing — stubs prove the interface works |

**End state:** Every trace gets evidence automatically. Looking at the broken-retrieval trace, the `RetrieverEvidenceProducer` shows severity 0.91. The `PromptEvidenceProducer` shows severity 0.12. The `LLMEvidenceProducer` shows severity 0.78 (answer not grounded). Zero LLM calls so far — the system already "knows" something is wrong from pure deterministic code.

---

### Phase 5 — Historical Search & Reasoning (Days 19–23)

**Goal:** Add memory and intelligence. The system should now not only detect anomalies but diagnose them and explain them.

| Day | Focus | You will learn |
|---|---|---|
| 19 | `HistoricalIncidents` table with pgvector `embedding vector(1536)` column; write the embedding step (summarize evidence + root cause into text, embed it using Groq/sentence-transformers) | What makes a good incident summary for embedding — this is real prompt-engineering craft |
| 20 | Implement pgvector cosine similarity search (`ORDER BY embedding <=> $1 LIMIT 5`); manually seed 2–3 historical incidents | Cold-start problem in recommendation systems; how to bootstrap "memory" on day one |
| 21 | `LLMProvider` interface + `GroqProvider` implementation; write the Reasoning module's prompt template (structured JSON output format) | Structured-output prompting; why the LLM prompt template is as important as the code |
| 22 | Wire Reasoning Engine into the worker pipeline; store results in `RootCauseReports` + `Recommendations`; test against broken scenarios | Does the LLM's diagnosis match what you already knew was wrong from the evidence? |
| 23 | Buffer/catch-up; iterate on the prompt template based on Day 22 output quality | Prompt iteration against real test cases — the real eval loop |

**End state:** Full backend pipeline complete. A trace comes in → metrics extracted → evidence produced → historical incidents searched → LLM synthesizes diagnosis → root cause report + recommendations stored. The broken-retrieval trace now has a diagnosis that says "Retriever failure" with ~90% confidence. The system is now genuinely useful.

---

### Phase 6 — Replay Engine (Days 24–27)

**Goal:** Build the flagship feature. Only possible now because it reuses every module from Phases 2–5.

| Day | Focus | You will learn |
|---|---|---|
| 24 | `ReplayExecutions` table; `POST /api/v1/replay` endpoint contract (trace ID + config overrides in, replay job ID out); hard rule: replay NEVER writes to `Traces` | Sandbox isolation — this is the same concept as a staging environment |
| 25 | Implement replay executor: re-run retrieval + prompt + LLM with modified config against the same knowledge base; reuse Feature Extraction + Evidence Producer code paths | The payoff of clean module boundaries — replay calls the same modules, not new code |
| 26 | `ReplayComparisons`: diff original vs replay metrics; reuse the Reasoning Engine to generate "why the replay improved things" explanation | Reuse over rebuilding — if you need to write new code to explain a replay, your earlier module boundaries leaked |
| 27 | Test a full replay loop: take the broken-retrieval trace, set `top_k=10`, replay it, confirm the correct doc now appears, confirm the comparison shows improved groundedness | Validating the flagship feature against known ground truth |

**End state:** You can take a specific failed conversation, change Top-K from 5 to 10, replay it, and see a side-by-side comparison showing the refund policy document now appears in retrieval and groundedness jumps from 0.52 to 0.94.

---

### Phase 7 — Frontend & Polish (Days 28–30)

**Goal:** Turn everything that currently exists only as API responses and SQL rows into something a human can look at and understand.

| Day | Focus | You will learn |
|---|---|---|
| 28 | Trace Explorer page: list of traces, click-through to Trace Detail with timeline, evidence cards, root cause report, Replay button | Where most "is this readable to someone else" work happens — frontend is not an afterthought |
| 29 | Replay page: split-screen comparison UI (original left, replay right, metrics diff); Historical Incidents page (searchable list) | Translating a structured diff object into a visual that communicates clearly |
| 30 | Minimal Dashboard (failure category bar chart, latency/cost trends); fresh cold-deploy test from scratch; honest README (what's V1, what's deferred); self-demo with all three broken scenarios | Closing the loop — confirming the whole system works as a coherent product, not just working modules |

**End state:** A live hosted website where you can view trace executions, see evidence-backed root cause diagnoses, replay a failed trace with different config, and see the before/after comparison — all with real data from your local RAG test app.

---

### Buffer strategy
Days marked as "buffer/catch-up" are intentional slack. If Phase 4 takes 6 days instead of 5, Phase 5 starts on Day 19 regardless. The phases don't depend on calendar dates — they depend on each other. Don't compress a phase to hit a date; compress a phase only if the goal ("something runnable") has genuinely been achieved.

---

## 17. How to Use This Document in a New Chat

Open a new conversation, paste this entire document (or share it as context), and begin with:

```
I am building the AI Engineering Copilot project described in this document.
I have completed up to [Day X / Phase Y].
Please guide me through Day [N].
```

The assistant should then give you that day's concrete tasks, the code to write, and the explanation of why each piece works the way it does.

### What the assistant needs to know per session
- Which day you're starting
- Where you got to last session (if a day ran long)
- Any blockers or questions from the previous session

### Quick-reference: tech stack
| Concern | Technology |
|---|---|
| Backend framework | FastAPI (Python) |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Background jobs | `arq` (async Redis job queue) |
| Database | PostgreSQL + pgvector |
| Vector search | pgvector (`embedding <=> query` cosine distance) |
| Hosting — backend | Render or Fly.io (free tier) |
| Hosting — frontend | Vercel |
| Hosting — DB | Neon or Supabase (free tier) |
| Hosting — Redis | Upstash (free tier) |
| LLM | Groq API (free tier, Llama 3.3 70B) |
| Frontend | React + TypeScript |
| Auth | Self-rolled JWT |

### Design rules to never break
1. Ingestion API always returns within ~100ms — no slow work in the request path
2. Evidence producers never determine root cause — they only report observations
3. LLM receives structured evidence only — never the raw trace
4. Replays never write to the `Traces` table — only to `ReplayExecutions`
5. Module imports are one-directional — `evidence/` can import `features/`, never vice versa
6. Every table has `org_id` — every query filters by it
7. All external dependencies (LLM, vector store) are behind interfaces in `core/`
