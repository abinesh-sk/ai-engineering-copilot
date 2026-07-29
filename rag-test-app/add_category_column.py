import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS category TEXT;")

# Map each source file to its category. Adjust filenames here if yours differ.
category_map = {
    "return_policy.txt": "returns",
    "shipping_policy.txt": "shipping",
    "warranty_policy.txt": "warranty",
}

for source_file, category in category_map.items():
    cur.execute(
        "UPDATE documents SET category = %s WHERE source_file = %s;",
        (category, source_file),
    )
    print(f"Set category='{category}' for {source_file}")

conn.commit()

# Sanity check: confirm every row got a category, none left NULL
cur.execute("SELECT category, COUNT(*) FROM documents GROUP BY category;")
print("\n--- Category counts ---")
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()