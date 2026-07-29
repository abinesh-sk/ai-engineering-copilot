from retrieval import retrieve
from generation import generate

query = "Can I return Product X? It is within the 30-day return period."

print("=== BAD CHUNKING retrieval (top_k=3) ===")
bad_results, _ = retrieve(query, top_k=3, table="documents_bad_chunking")
for r in bad_results:
    print(f"[{r['similarity']:.3f}] chunk {r['chunk_index']}: {r['content']!r}")

print("\n=== GOOD CHUNKING retrieval (top_k=3), for comparison ===")
good_results, _ = retrieve(query, top_k=3, table="documents")
for r in good_results:
    print(f"[{r['similarity']:.3f}] chunk {r['chunk_index']}: {r['content'][:100]!r}...")

print("\n=== Generation using BAD CHUNKING chunks ===")
result = generate(query, bad_results)
print(result["answer"])