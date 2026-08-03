from app.core.database import SessionLocal
from app.trace.models import Trace
from app.features.models import TraceMetrics
from app.features.retrieval_extractor import extract_retrieval_metrics
from app.features.prompt_extractor import extract_prompt_metrics
from app.features.latency_cost_extractor import extract_latency_cost_metrics


def process_trace_job(trace_id: str):
    print(f"[worker] Received job for trace_id: {trace_id}")

    db = SessionLocal()
    try:
        trace = db.query(Trace).filter(Trace.id == trace_id).first()
        if trace is None:
            print(f"[worker] No trace found for {trace_id}, skipping")
            return

        spans = trace.spans
        retrieval_span = next((s for s in spans if s.span_type == "retrieval"), None)
        llm_span = next((s for s in spans if s.span_type == "llm_call"), None)

        retrieval_metrics = (
            extract_retrieval_metrics(retrieval_span.raw_data)
            if retrieval_span is not None
            else {"avg_similarity": None, "max_similarity": None, "min_similarity": None, "chunk_count": None}
        )
        prompt_metrics = (
            extract_prompt_metrics(llm_span.raw_data)
            if llm_span is not None
            else {"prompt_length_chars": None, "context_length_chars": None, "prompt_tokens": None, "completion_tokens": None}
        )
        latency_cost_metrics = extract_latency_cost_metrics(trace, spans)

        all_metrics = {**retrieval_metrics, **prompt_metrics, **latency_cost_metrics}

        existing = db.query(TraceMetrics).filter(TraceMetrics.trace_id == trace_id).first()
        if existing is not None:
            for key, value in all_metrics.items():
                setattr(existing, key, value)
        else:
            db.add(TraceMetrics(trace_id=trace_id, **all_metrics))

        trace.status = "extracted"
        db.commit()
        print(f"[worker] Feature extraction complete for {trace_id}: {all_metrics}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()