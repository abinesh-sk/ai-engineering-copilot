"""
Feature Extraction: Day 12 -- latency/cost metrics.

Pure function. Unlike Days 10-11, these numbers aren't buried in a span's
raw_data -- total_latency_ms/total_cost_usd already live on Trace itself
(post_trace.py computes them), and latency_ms is already a real column on
each TraceSpan. This extractor's only job is picking the right numbers off
the right rows and giving them one consistent shape for TraceMetrics.
"""


def extract_latency_cost_metrics(trace, spans) -> dict:
    retrieval_latency_ms = None
    llm_latency_ms = None

    for span in spans:
        if span.span_type == "retrieval":
            retrieval_latency_ms = span.latency_ms
        elif span.span_type == "llm_call":
            llm_latency_ms = span.latency_ms

    return {
        "retrieval_latency_ms": retrieval_latency_ms,
        "llm_latency_ms": llm_latency_ms,
        "total_latency_ms": trace.total_latency_ms,
        "total_cost_usd": trace.total_cost_usd,
    }