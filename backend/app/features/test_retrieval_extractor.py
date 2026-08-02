from app.core.database import SessionLocal
from app.trace.models import Trace, TraceSpan
from app.features.retrieval_extractor import extract_retrieval_metrics

TRACE_ID = "1db70bc2-af97-4be9-bf32-e326eae840c4"

db = SessionLocal()
try:
    span = (
        db.query(TraceSpan)
        .filter(TraceSpan.trace_id == TRACE_ID, TraceSpan.span_type == "retrieval")
        .first()
    )
    if span is None:
        print(f"No retrieval span found for trace {TRACE_ID}")
    else:
        metrics = extract_retrieval_metrics(span.raw_data)
        print(metrics)
finally:
    db.close()