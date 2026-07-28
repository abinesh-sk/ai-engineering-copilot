import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("SELECT source_file, COUNT(*) FROM documents GROUP BY source_file ORDER BY source_file;")
print("Chunks per file:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} chunks")

cur.execute("SELECT COUNT(*) FROM documents;")
print(f"\nTotal chunks: {cur.fetchone()[0]}")

cur.execute("SELECT content FROM documents WHERE source_file = 'return_policy.txt' AND content ILIKE '%Product X%' LIMIT 1;")
result = cur.fetchone()
print(f"\nSample chunk mentioning Product X:\n{result[0] if result else 'NOT FOUND'}")

cur.close()
conn.close()