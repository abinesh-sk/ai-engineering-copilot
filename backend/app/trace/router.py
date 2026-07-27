from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.trace.models import Trace, TraceSpan
from app.trace.schemas import TraceCreate, TraceOut

from app.core.queue import job_queue

router = APIRouter(prefix="/api/v1/traces", tags=["traces"])


@router.post("", response_model=TraceOut, status_code=201)
def create_trace(payload: TraceCreate, db: Session = Depends(get_db)):
    trace = Trace(
        org_id=payload.org_id,
        application_id=payload.application_id,
        user_query=payload.user_query,
        final_answer=payload.final_answer,
        total_latency_ms=payload.total_latency_ms,
        total_cost_usd=payload.total_cost_usd,
        status="ingested",
    )
    db.add(trace)
    db.flush()  # trace.id now exists, without committing yet

    for span_in in payload.spans:
        span = TraceSpan(
            trace_id=trace.id,
            span_type=span_in.span_type,
            sequence=span_in.sequence,
            latency_ms=span_in.latency_ms,
            raw_data=span_in.raw_data,
        )
        db.add(span)

    db.commit()
    db.refresh(trace)  # reload trace + its spans relationship from DB
    job_queue.enqueue("app.core.jobs.process_trace_job", str(trace.id))
    return trace


@router.get("/{trace_id}", response_model=TraceOut)
def get_trace(trace_id: str, db: Session = Depends(get_db)):
    trace = db.get(Trace, trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace