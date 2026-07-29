from retrieval import retrieve

candidates = [
    "I don't want Product X anymore, can I send it back for a refund?",
    "I changed my mind about Product X, is it returnable?",
    "Can I return Product X if I just don't need it, nothing wrong with it?",
]

for q in candidates:
    print(f"\n=== Query: {q} ===")
    results, _ = retrieve(q, top_k=5)
    for i, r in enumerate(results, start=1):
        print(f"  rank {i}: sim={r['similarity']:.3f}  source={r['source_file']}  chunk_idx={r['chunk_index']}")
        print(f"           {r['content'][:80]}...")