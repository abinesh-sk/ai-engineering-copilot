from typing import Optional


def extract_retrieval_metrics(retrieval_span_raw_data: dict) -> dict:
    """
    Pure translation, no judgment: reads a retrieval span's raw_data
    and returns flat, queryable numbers.

    Deliberately reads ONLY 'results' — never injected_failure /
    expected_correct_source / expected_correct_chunk_index. Those keys
    only exist on Day 8 scenario traces; a real production trace won't
    have them, and this function must behave identically either way.
    """
    results = retrieval_span_raw_data.get("results", [])

    if not results:
        # No chunks retrieved at all is itself meaningful (Day 14+ will
        # care), but Feature Extraction just reports the absence honestly
        # rather than guessing a default similarity.
        return {
            "avg_similarity": None,
            "max_similarity": None,
            "min_similarity": None,
            "chunk_count": 0,
        }

    similarities = [r["similarity"] for r in results]

    return {
        "avg_similarity": sum(similarities) / len(similarities),
        "max_similarity": max(similarities),
        "min_similarity": min(similarities),
        "chunk_count": len(results),
    }