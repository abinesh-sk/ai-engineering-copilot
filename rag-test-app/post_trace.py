import os
import requests
from dotenv import load_dotenv
from retrieval import retrieve
from generation import generate

load_dotenv()

ORG_ID = "ab6ed8df-5f97-428c-8d70-77773c676988"
APPLICATION_ID = "a3c12e69-94bf-48a5-9183-293356c59d47"

BACKEND_URL = "https://ai-engineering-copilot.onrender.com"

# Groq's published per-token pricing for llama-3.3-70b-versatile, used only to
# compute a realistic total_cost_usd for Feature Extraction later (Day 12) —
# actual usage here is still $0 under the free tier.
INPUT_COST_PER_TOKEN = 0.59 / 1_000_000
OUTPUT_COST_PER_TOKEN = 0.79 / 1_000_000


def run_and_post(query: str):
    retrieved_chunks, retrieval_latency_ms = retrieve(query)
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
    print(response.json())


if __name__ == "__main__":
    run_and_post("Can I return Product X? It is within the 30-day return period.")