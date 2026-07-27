from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.models import Base, new_uuid, utcnow


class Trace(Base):
    """
    One complete execution of a monitored AI application.
    This is what arrives via POST /api/v1/traces (Day 3).
    """
    __tablename__ = "traces"

    id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=False)
    application_id = Column(UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False)

    user_query = Column(String, nullable=False)
    final_answer = Column(String, nullable=True)

    status = Column(String, default="ingested")
    # lifecycle: ingested -> extracted -> evidence_generated -> diagnosed

    total_latency_ms = Column(Integer, nullable=True)
    total_cost_usd = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)

    spans = relationship("TraceSpan", back_populates="trace", cascade="all, delete-orphan")


class TraceSpan(Base):
    """
    One sub-step within a trace: retrieval, prompt construction, llm_call, tool_call, etc.
    raw_data holds whatever shape that span type naturally has (Feature Extraction
    reads this on Day 10-12; nothing before that stage needs to parse it).
    """
    __tablename__ = "trace_spans"

    id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    trace_id = Column(UUID(as_uuid=False), ForeignKey("traces.id"), nullable=False)

    span_type = Column(String, nullable=False)  # "retrieval" | "prompt" | "llm_call" | "tool_call"
    sequence = Column(Integer, nullable=False)   # order within the trace

    latency_ms = Column(Integer, nullable=True)
    raw_data = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)

    trace = relationship("Trace", back_populates="spans")