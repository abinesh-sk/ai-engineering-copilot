import uuid
from sqlalchemy import Column, Float, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.core.models import Base


class TraceMetrics(Base):
    __tablename__ = "trace_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("traces.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    
    # Retrieval metrics (Day 10)
    avg_similarity = Column(Float, nullable=True)
    max_similarity = Column(Float, nullable=True)
    min_similarity = Column(Float, nullable=True)
    chunk_count = Column(Integer, nullable=True)

    prompt_length_chars = Column(Integer, nullable=True)
    context_length_chars = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)