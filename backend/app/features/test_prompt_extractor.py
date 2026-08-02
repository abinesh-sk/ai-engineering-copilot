from app.core.database import SessionLocal
from app.trace.models import TraceSpan
from app.features.prompt_extractor import extract_prompt_metrics

TRACE_ID = "44291973-32d8-48a7-af28-997436a4d3ef"  # real llm_call span, Day 7 known-good trace

db = SessionLocal()
span = (
    db.query(TraceSpan)
    .filter(TraceSpan.trace_id == TRACE_ID, TraceSpan.span_type == "llm_call")
    .first()
)
print(extract_prompt_metrics(span.raw_data))
db.close()