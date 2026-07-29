import os
import time
import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

# Loaded once at import time — reused across calls, not reloaded per query
_model = SentenceTransformer("all-MiniLM-L6-v2")

def retrieve(query: str, top_k: int = 3, table: str = "documents", category: str | None = None):
    """
    Embeds the query, runs a pgvector cosine-similarity search against
    the given table (optionally restricted to a metadata category),
    and returns the top_k closest chunks along with similarity scores
    and how long retrieval took.
    """
    if table not in ("documents", "documents_bad_chunking"):
        raise ValueError(f"Unknown table: {table}")

    start = time.time()

    query_embedding = _model.encode(query).tolist()

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    if category is not None:
        cur.execute(
            f"""
            SELECT source_file, chunk_index, content,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM {table}
            WHERE category = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
            """,
            (query_embedding, category, query_embedding, top_k),
        )
    else:
        cur.execute(
            f"""
            SELECT source_file, chunk_index, content,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM {table}
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
            """,
            (query_embedding, query_embedding, top_k),
        )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    latency_ms = (time.time() - start) * 1000

    results = [
        {
            "source_file": r[0],
            "chunk_index": r[1],
            "content": r[2],
            "similarity": float(r[3]),
        }
        for r in rows
    ]

    return results, latency_ms

if __name__ == "__main__":
    results, latency_ms = retrieve("Can I return Product X? It is within the 30-day return period.")
    print(f"Retrieval took {latency_ms:.1f}ms\n")
    for r in results:
        print(f"[{r['similarity']:.3f}] {r['source_file']} chunk {r['chunk_index']}")
        print(f"  {r['content'][:100]}...\n")