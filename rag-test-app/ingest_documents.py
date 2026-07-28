import os
import glob
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import psycopg2

load_dotenv()

# --- Chunking ---
# Paragraph-based chunking: split on blank lines. Each policy document's
# paragraphs are already self-contained units of meaning (one rule per
# paragraph), so this is a natural, low-effort chunk boundary — no
# mid-sentence splits, no arbitrary character counts.
def chunk_document(text: str) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return paragraphs

# --- Embedding ---
# Local model, no API call, no cost. 384-dim output vectors, matching the
# VECTOR(384) column created in create_table.py.
print("Loading embedding model (first run downloads ~90MB, then cached)...")
model = SentenceTransformer("all-MiniLM-L6-v2")

# --- Storage ---
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

# Clear existing rows so re-running this script doesn't duplicate chunks
cur.execute("TRUNCATE TABLE documents RESTART IDENTITY;")

doc_paths = glob.glob("documents/*.txt")
total_chunks = 0

for path in doc_paths:
    filename = os.path.basename(path)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    chunks = chunk_document(text)
    print(f"{filename}: {len(chunks)} chunks")

    for i, chunk in enumerate(chunks):
        embedding = model.encode(chunk).tolist()
        cur.execute(
            """
            INSERT INTO documents (source_file, chunk_index, content, embedding)
            VALUES (%s, %s, %s, %s)
            """,
            (filename, i, chunk, embedding),
        )
        total_chunks += 1

conn.commit()
cur.close()
conn.close()

print(f"Done. Inserted {total_chunks} chunks total.")