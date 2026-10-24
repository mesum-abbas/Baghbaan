
import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "knowledge_base" / "candidate_facts.json"
OUTPUT_FILE = BASE_DIR / "knowledge_base" / "fact_review_queue.csv"

with INPUT_FILE.open("r", encoding="utf-8") as file:
    facts = json.load(file)

columns = [
    "fact_id",
    "plant_id",
    "plant_name",
    "candidate_text",
    "topic_candidates",
    "source_type",
    "source_id",
    "source_url",
    "verification_result",
    "corrected_fact",
    "reviewer_notes",
    "cross_checked_source_url",
]

with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as file:
    writer = csv.DictWriter(file, fieldnames=columns)
    writer.writeheader()

    for fact in facts:
        writer.writerow({
            "fact_id": fact.get("fact_id", ""),
            "plant_id": fact.get("plant_id", ""),
            "plant_name": fact.get("plant_name", ""),
            "candidate_text": fact.get("candidate_text", ""),
            "topic_candidates": ", ".join(
                fact.get("topic_candidates", [])
            ) if isinstance(fact.get("topic_candidates"), list)
            else fact.get("topic_candidates", ""),
            "source_type": fact.get("source_type", ""),
            "source_id": fact.get("source_id", ""),
            "source_url": fact.get("source_url", ""),
            "verification_result": "pending",
            "corrected_fact": "",
            "reviewer_notes": "",
            "cross_checked_source_url": "",
        })

print(f"Total facts exported: {len(facts)}")
print(f"Review file created: {OUTPUT_FILE}")
