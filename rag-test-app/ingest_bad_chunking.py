import os
import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

CHUNK_SIZE = 120  # deliberately small, arbitrary — no awareness of sentence boundaries

_model = SentenceTransformer("all-MiniLM-L6-v2")

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

# Wipe any previous run so this stays idempotent, matching your ingest_documents.py pattern
cur.execute("DELETE FROM documents_bad_chunking WHERE source_file = 'return_policy.txt';")

with open("documents/return_policy.txt", "r", encoding="utf-8") as f:
    text = f.read()

chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

for idx, chunk in enumerate(chunks):
    embedding = _model.encode(chunk).tolist()
    cur.execute(
        """
        INSERT INTO documents_bad_chunking (source_file, chunk_index, content, embedding)
        VALUES (%s, %s, %s, %s::vector);
        """,
        ("return_policy.txt", idx, chunk, embedding),
    )

conn.commit()
cur.close()
conn.close()

print(f"Inserted {len(chunks)} fixed-size chunks from return_policy.txt")
print("\n--- Chunk preview ---")
for idx, chunk in enumerate(chunks):
    marker = " <-- contains 'Product X'" if "Product X" in chunk else ""
    print(f"[{idx}] {chunk!r}{marker}")