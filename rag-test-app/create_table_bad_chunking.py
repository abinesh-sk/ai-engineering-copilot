import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS documents_bad_chunking (
        id SERIAL PRIMARY KEY,
        source_file TEXT NOT NULL,
        chunk_index INT NOT NULL,
        content TEXT NOT NULL,
        embedding VECTOR(384) NOT NULL
    );
""")

conn.commit()
cur.close()
conn.close()
print("documents_bad_chunking table ready.")