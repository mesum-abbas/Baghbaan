
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "knowledge_base"

PLANTS_FILE = KB_DIR / "plants.json"
COVERAGE_FILE = KB_DIR / "coverage_matrix.json"
CANDIDATES_FILE = KB_DIR / "candidate_facts.json"
SOURCES_FILE = KB_DIR / "sources.json"

def load_json(path):
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)

def main():
    plants = load_json(PLANTS_FILE)
    coverage = load_json(COVERAGE_FILE)
    candidates = load_json(CANDIDATES_FILE)
    sources = load_json(SOURCES_FILE)

    print("\n=== PLANTCARE RESEARCH VALIDATION ===")
    print("Plants registered:", len(plants))
    print("Sources registered:", len(sources))
    print("Candidate facts:", len(candidates))

    source_ids = {source["source_id"] for source in sources}
    plant_counts = Counter(
        fact.get("plant_name", "Unknown")
        for fact in candidates
    )
    source_types = Counter(
        fact.get("source_type", "Unknown")
        for fact in candidates
    )

    print("\n=== CANDIDATES PER PLANT ===")
    for plant, count in plant_counts.items():
        print(f"{plant}: {count}")

    print("\n=== SOURCE TYPES ===")
    for source_type, count in source_types.items():
        print(f"{source_type}: {count}")

    missing_sources = [
        fact.get("fact_id", "Unknown")
        for fact in candidates
        if fact.get("source_id")
        and fact["source_id"] not in source_ids
    ]

    print("\n=== PROVENANCE CHECK ===")
    print("Candidates with unknown source IDs:", len(missing_sources))
    if missing_sources:
        print("Examples:", ", ".join(missing_sources[:10]))

    approved = [
        fact for fact in candidates
        if fact.get("approved_for_knowledge_base") is True
    ]
    print("\nCandidates marked approved:", len(approved))

    print("\n=== COVERAGE MATRIX STATUS ===")
    print(json.dumps(coverage, indent=2, ensure_ascii=False))

    print("\nValidation report completed.")
    print("This script does not approve, delete, or modify any facts.")

if __name__ == "__main__":
    main()

