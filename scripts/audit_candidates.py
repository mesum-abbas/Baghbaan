
import csv
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "knowledge_base" / "fact_review_queue.csv"

with INPUT_FILE.open("r", encoding="utf-8-sig", newline="") as file:
    rows = list(csv.DictReader(file))

print("TOTAL CANDIDATES:", len(rows))
print("\nFACTS PER PLANT:")

plant_counts = Counter(row["plant_name"] for row in rows)
for plant, count in plant_counts.items():
    print(f"{plant}: {count}")

print("\nSOURCE TYPES:")
for source, count in Counter(
    row["source_type"] for row in rows
).items():
    print(f"{source or 'Unknown'}: {count}")

print("\nFIRST 20 CANDIDATES FOR MANUAL AUDIT:")
for row in rows[:20]:
    print("-" * 70)
    print("ID:", row["fact_id"])
    print("Plant:", row["plant_name"])
    print("Topic:", row["topic_candidates"])
    print("Source:", row["source_type"], row["source_id"])
    print("Fact:", row["candidate_text"])
    print("URL:", row["source_url"])

