from retrieval import retrieve
from generation import generate

query = "Can I return Product X? It is within the 30-day return period."

print("=== WRONG category filter ('warranty') ===")
wrong_results, _ = retrieve(query, top_k=3, category="warranty")
for r in wrong_results:
    print(f"[{r['similarity']:.3f}] {r['source_file']} chunk {r['chunk_index']}: {r['content'][:80]!r}...")

print("\n=== CORRECT category filter ('returns'), for comparison ===")
correct_results, _ = retrieve(query, top_k=3, category="returns")
for r in correct_results:
    print(f"[{r['similarity']:.3f}] {r['source_file']} chunk {r['chunk_index']}: {r['content'][:80]!r}...")

print("\n=== Generation using WRONG category results ===")
result = generate(query, wrong_results)
print(result["answer"])