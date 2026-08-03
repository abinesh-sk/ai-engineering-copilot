"""
Day 13: manually re-enqueue extraction jobs for Day 8's broken-scenario
traces. These were posted before the worker did real extraction (Day 12),
so they have spans but no TraceMetrics row yet.
"""
from app.core.queue import job_queue
from app.core.jobs import process_trace_job

BROKEN_SCENARIO_TRACE_IDS = {
    "bad_metadata_filter": "1db70bc2-af97-4be9-bf32-e326eae840c4",
    "bad_chunking": "19737bf3-ed88-4879-bf6b-27f87c89be3a",
    "low_top_k": "3ae36bb8-ed23-43e1-849e-8174f830107a",
}

for scenario, trace_id in BROKEN_SCENARIO_TRACE_IDS.items():
    job_queue.enqueue(process_trace_job, trace_id)
    print(f"Enqueued {scenario}: {trace_id}")