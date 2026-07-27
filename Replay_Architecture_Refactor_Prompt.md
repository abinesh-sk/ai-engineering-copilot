# Replay Architecture Refactor Prompt for Claude

I want to improve the architecture of my **AI Engineering Copilot**
project to make it deployable as a real SaaS product that can integrate
with **external AI/RAG applications**, not just my local test RAG
application.

## Current V1 Architecture

Currently, the Replay Engine assumes that the platform owns the RAG
application. It reconstructs the pipeline and directly re-executes
retrieval, prompt building, and the LLM call inside a sandbox. This
works because my V1 project includes a local `rag_test_app` that I
control.

However, this architecture does **not** generalize to real customers.

## Problem

Imagine I sell AI Engineering Copilot to a company that already has a
production RAG chatbot.

My platform only receives traces through:

``` text
POST /api/v1/traces
```

The company owns:

-   Retriever
-   Vector Database
-   Embedding Model
-   Prompt Builder
-   LLM
-   Knowledge Base

My platform does **not**.

Therefore my Replay Engine cannot simply "reconstruct and replay" their
pipeline because it has no access to any of these components.

A trace is only historical execution data, not an executable pipeline.

## Desired SaaS Architecture

I want to redesign only the **Replay architecture** while preserving
every other module.

Instead of the Replay Engine directly executing the pipeline, I want a
new abstraction:

``` text
Replay Engine
        │
        ▼
ReplayAdapter Interface
        │
 ┌──────┴──────────────┐
 │                     │
 ▼                     ▼
LocalReplayAdapter     SDKReplayAdapter
(V1)                   (Production)
```

Future adapters might include:

-   LocalReplayAdapter (current V1 rag_test_app)
-   SDKReplayAdapter (customer installs our SDK)
-   RESTReplayAdapter (customer exposes replay endpoint)
-   LangGraphReplayAdapter
-   LlamaIndexReplayAdapter
-   HaystackReplayAdapter

The Replay Engine should know nothing about how replay actually happens.

It should only call:

``` python
ReplayAdapter.replay(
    trace_id,
    config_overrides
)
```

and receive a standardized `ReplayResult`.

## Production Flow

Instead of replay happening inside my platform, it should work like
this:

``` text
Company RAG
      │
      ▼
Our SDK
      │
      ▼
POST /api/v1/traces
      │
      ▼
AI Engineering Copilot
```

When the engineer clicks **Replay**:

``` text
AI Engineering Copilot
      │
      ▼
ReplayAdapter
      │
      ▼
Customer SDK / Replay API
      │
      ▼
Customer RAG Pipeline
      │
      ▼
Runs replay with modified configuration
      │
      ▼
Produces a new trace
      │
      ▼
POST /api/v1/replay-result
      │
      ▼
AI Engineering Copilot
```

The customer's infrastructure performs the replay because it has access
to:

-   Retriever
-   Vector DB
-   Prompt Builder
-   Embedding Model
-   LLM
-   Knowledge Base

My platform never directly executes customer pipelines.

## Requirements

Please modify the design document accordingly.

Specifically:

1.  Preserve the existing V1 functionality using `LocalReplayAdapter`.
2.  Introduce a `ReplayAdapter` abstraction similar to the existing
    `LLMProvider` and `VectorStore` abstractions.
3.  Rewrite the Replay Engine section to support both:
    -   Local replay (V1)
    -   SaaS replay through customer SDK/API.
4.  Add a new section describing:
    -   Replay SDK
    -   Replay API contract
    -   ReplayAdapter interface
    -   ReplayResult model
5.  Explain why this design is more vendor-independent and scalable.
6.  Update the architecture diagrams where necessary.
7.  Keep all other architectural decisions unchanged.

The final design should remain interview-quality, modular, extensible,
and production-oriented while remaining fully compatible with the
current V1 implementation.
