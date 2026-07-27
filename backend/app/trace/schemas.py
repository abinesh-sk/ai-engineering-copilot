from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class SpanIn(BaseModel):
    """One span as submitted by the client when POSTing a trace."""
    span_type: str
    sequence: int
    latency_ms: Optional[int] = None
    raw_data: Optional[dict[str, Any]] = None


class TraceCreate(BaseModel):
    """What a client is allowed to send us — nothing server-generated."""
    org_id: str
    application_id: str
    user_query: str
    final_answer: Optional[str] = None
    total_latency_ms: Optional[int] = None
    total_cost_usd: Optional[float] = None
    spans: list[SpanIn] = []


class SpanOut(BaseModel):
    id: str
    span_type: str
    sequence: int
    latency_ms: Optional[int]
    raw_data: Optional[dict[str, Any]]

    class Config:
        from_attributes = True  # lets Pydantic read this straight off a SQLAlchemy object


class TraceOut(BaseModel):
    """What we hand back to the client — includes server-generated fields."""
    id: str
    org_id: str
    application_id: str
    user_query: str
    final_answer: Optional[str]
    status: str
    total_latency_ms: Optional[int]
    total_cost_usd: Optional[float]
    created_at: datetime
    spans: list[SpanOut] = []

    class Config:
        from_attributes = True