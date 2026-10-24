
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "knowledge_base"

with (KB / "candidate_facts.json").open(
    "r", encoding="utf-8-sig"
) as f:
    candidates = json.load(f)

# Keep only excerpts that may help diagnose plant problems.
diagnostic_terms = [
    "yellow", "wilting", "wilt", "droop", "brown",
    "leaf tip", "leaf spot", "pest", "insect",
    "root rot", "overwater", "underwater", "waterlogged",
    "watering", "drainage", "humidity", "fungal",
    "disease", "growth", "light", "sunlight",
    "fertilizer", "nutrient", "symptom", "damage"
]

filtered = []
for fact in candidates:
    text = fact.get("candidate_text", "").lower()

    if any(term in text for term in diagnostic_terms):
        item = fact.copy()
        item["filter_status"] = "needs_manual_review"
        filtered.append(item)

output = KB / "filtered_candidates.json"
with output.open("w", encoding="utf-8") as f:
    json.dump(filtered, f, indent=2, ensure_ascii=False)

print("Original candidates:", len(candidates))
print("Potentially relevant candidates:", len(filtered))
print("By source type:", dict(Counter(
    x.get("source_type", "Unknown") for x in filtered
)))
print("Saved to:", output)
print("Reminder: filtering is not evidence verification.")
