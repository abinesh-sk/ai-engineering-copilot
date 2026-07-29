import os
import requests
from dotenv import load_dotenv
from retrieval import retrieve
from generation import generate

load_dotenv()

ORG_ID = "ab6ed8df-5f97-428c-8d70-77773c676988"
APPLICATION_ID = "a3c12e69-94bf-48a5-9183-293356c59d47"

BACKEND_URL = "https://ai-engineering-copilot.onrender.com"

INPUT_COST_PER_TOKEN = 0.59 / 1_000_000
OUTPUT_COST_PER_TOKEN = 0.79 / 1_000_000


def run_and_post(
    query: str,
    top_k: int = 3,
    table: str = "documents",
    category: str | None = None,
    scenario: str | None = None,
    expected_correct_source: str | None = None,
    expected_correct_chunk_index: int | None = None,
):
    retrieved_chunks, retrieval_latency_ms = retrieve(query, top_k=top_k, table=table, category=category)
    result = generate(query, retrieved_chunks)

    total_latency_ms = retrieval_latency_ms + result["latency_ms"]
    total_cost_usd = (
        result["prompt_tokens"] * INPUT_COST_PER_TOKEN
        + result["completion_tokens"] * OUTPUT_COST_PER_TOKEN
    )

    trace_payload = {
        "org_id": ORG_ID,
        "application_id": APPLICATION_ID,
        "user_query": query,
        "final_answer": result["answer"],
        "total_latency_ms": int(total_latency_ms),
        "total_cost_usd": total_cost_usd,
        "spans": [
            {
                "span_type": "retrieval",
                "sequence": 0,
                "latency_ms": int(retrieval_latency_ms),
                "raw_data": {
                    "query": query,
                    "top_k": len(retrieved_chunks),
                    "results": retrieved_chunks,
                    # Ground-truth markers for Day 8 failure injection.
                    # Real production traces will simply not have this key.
                    "injected_failure": scenario,
                    "expected_correct_source": expected_correct_source,
                    "expected_correct_chunk_index": expected_correct_chunk_index,
                },
            },
            {
                "span_type": "llm_call",
                "sequence": 1,
                "latency_ms": int(result["latency_ms"]),
                "raw_data": {
                    "model": "llama-3.3-70b-versatile",
                    "temperature": 0.2,
                    "prompt": result["prompt"],
                    "answer": result["answer"],
                    "prompt_tokens": result["prompt_tokens"],
                    "completion_tokens": result["completion_tokens"],
                },
            },
        ],
    }

    response = requests.post(f"{BACKEND_URL}/api/v1/traces", json=trace_payload)
    print(f"Status: {response.status_code}")
    print(f"Scenario: {scenario or 'baseline (known-good)'}")
    print(response.json())
    return response

if __name__ == "__main__":
    # Scenario 1: Low Top-K
    # Query is a plain "changed my mind" return with no damage involved.
    # The damage-exception chunk (idx=3) wins rank 1 purely on lexical
    # overlap ("Product X", "refund"), while the chunk that actually
    # answers this question (Non-Returnable Categories, idx=2) ranks #2.
    # top_k=1 truncates it out, so the LLM only sees an irrelevant
    # exception clause for a query it doesn't apply to.
    run_and_post(
        query="I don't want Product X anymore, can I send it back for a refund?",
        top_k=1,
        scenario="low_top_k",
        expected_correct_source="return_policy.txt",
        expected_correct_chunk_index=2,
    )
    # Scenario 2: Bad Chunking
    # return_policy.txt was re-ingested into documents_bad_chunking using a
    # fixed 120-char chunker with no sentence/paragraph awareness, splitting
    # the Non-Returnable Categories paragraph into 4 disconnected fragments.
    # Retrieval still finds Product X-related fragments, but they're
    # decontextualized — the LLM hedges instead of stating the clear rule
    # it states when given the intact paragraph (see documents table).
    run_and_post(
        query="Can I return Product X? It is within the 30-day return period.",
        top_k=3,
        table="documents_bad_chunking",
        scenario="bad_chunking",
        expected_correct_source="return_policy.txt",
        expected_correct_chunk_index=2,  # the intact chunk in the GOOD table
    )
    # Scenario 3: Bad Metadata Filtering
    # Application code passes category="warranty" instead of "returns" for a
    # plain Product X return question (a plausible bug, since Product X also
    # appears in the warranty doc). return_policy.txt is excluded from the
    # candidate pool BEFORE similarity search runs, so no ranking or chunking
    # quality could have saved this — the correct document was never a
    # candidate at all.
    run_and_post(
        query="Can I return Product X? It is within the 30-day return period.",
        top_k=3,
        category="warranty",
        scenario="bad_metadata_filter",
        expected_correct_source="return_policy.txt",
        expected_correct_chunk_index=2,
    )