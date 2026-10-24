
import json
import re
import html
import hashlib
from pathlib import Path
from difflib import SequenceMatcher

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "knowledge_base"

WIKI_FILE = KB_DIR / "raw_wikipedia.json"
DOCS_FILE = KB_DIR / "raw_documents.json"

CLEAN_FILE = KB_DIR / "cleaned_research.json"
CANDIDATES_FILE = KB_DIR / "candidate_facts.json"

# These terms help shortlist care-related text.
# They do NOT prove a statement is correct.
CARE_TERMS = {
    "watering", "water", "overwater", "underwater", "moisture",
    "soil", "drainage", "root rot", "root", "light", "sunlight",
    "shade", "temperature", "humidity", "fertilizer", "nutrient",
    "yellow", "wilting", "wilt", "drooping", "brown", "leaf tip",
    "leaves", "spots", "pest", "insect", "mite", "fungus",
    "fungal", "disease", "growth", "growing", "propagation",
    "pot", "repot", "symptom", "toxic", "chlorosis", "decay",
}

# Common text that is usually not useful for diagnosis.
NOISE_PHRASES = (
    "jump to content",
    "toggle the table of contents",
    "edit section",
    "citation needed",
    "coordinates:",
    "isbn ",
    "doi:",
    "retrieved from",
    "wikimedia commons",
)


def load_json(path):
    if not path.exists():
        print(f"WARNING: Missing file: {path.name}")
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"ERROR reading {path.name}: {error}")
        return []

    if not isinstance(data, list):
        print(f"WARNING: {path.name} should contain a JSON list.")
        return []

    return data


def clean_text(value):
    """Normalize text without changing its underlying meaning."""
    if not isinstance(value, str):
        return ""

    value = html.unescape(value)
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def is_noise(text):
    lowered = text.casefold()

    if len(lowered) < 35:
        return True

    return any(phrase in lowered for phrase in NOISE_PHRASES)


def is_care_relevant(text):
    lowered = text.casefold()
    return any(term in lowered for term in CARE_TERMS)


def make_hash(text):
    normalized = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def split_sentences(text):
    """Basic sentence splitting; review candidates before using them."""
    text = clean_text(text)

    if not text:
        return []

    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    return [part.strip() for part in parts if part.strip()]


def get_plant_info(source, source_type):
    plant_id = source.get("plant_id", "")
    plant_name = source.get("plant_name", "")

    if source_type == "horticulture":
        source_id = source.get("source_id", "")
        plant_map = {
            "PLSRC001": ("PLANT001", "Money Plant"),
            "PLSRC002": ("PLANT002", "Snake Plant"),
            "PLSRC003": ("PLANT003", "Aloe Vera"),
            "PLSRC004": ("PLANT004", "Spider Plant"),
            "PLSRC005": ("PLANT005", "Peace Lily"),
        }

        if source_id in plant_map:
            plant_id, plant_name = plant_map[source_id]

    return plant_id, plant_name


def add_candidate(
    candidates,
    seen_hashes,
    text,
    plant_id,
    plant_name,
    source_url,
    source_type,
    source_id="",
    context="",
):
    text = clean_text(text)

    if is_noise(text) or not is_care_relevant(text):
        return

    fingerprint = make_hash(text)

    # Exact duplicates are skipped; source provenance of the
    # first matching record remains attached to that candidate.
    if fingerprint in seen_hashes:
        return

    seen_hashes.add(fingerprint)

    candidates.append({
        "fact_id": f"FACT{len(candidates) + 1:05d}",
        "plant_id": plant_id,
        "plant_name": plant_name,
        "candidate_text": text,
        "topic_candidates": [
            term for term in sorted(CARE_TERMS)
            if term in text.casefold()
        ],
        "source_url": source_url,
        "source_type": source_type,
        "source_id": source_id,
        "context": context,
        "content_hash": fingerprint,
        "review_status": "needs_verification",
        "verification_notes": "",
        "approved_for_knowledge_base": False,
    })


def process_wikipedia(records, candidates, seen_hashes, cleaned):
    for source in records:
        if source.get("status") != "collected":
            continue

        plant_id = source.get("plant_id", "")
        plant_name = source.get("plant_name", "")
        source_url = source.get("source_url", "")
        text = clean_text(source.get("text", ""))

        cleaned.append({
            "record_type": "article",
            "plant_id": plant_id,
            "plant_name": plant_name,
            "source_url": source_url,
            "source_type": "Wikipedia",
            "revision_id": source.get("revision_id"),
            "retrieved_at": source.get("retrieved_at", ""),
            "word_count": len(text.split()),
            "cleaned_text": text,
            "review_status": "needs_manual_review",
        })

        for sentence in split_sentences(text):
            add_candidate(
                candidates,
                seen_hashes,
                sentence,
                plant_id,
                plant_name,
                source_url,
                "Wikipedia",
                context=source.get("wiki_title", ""),
            )


def process_horticulture(records, candidates, seen_hashes, cleaned):
    for source in records:
        status = source.get("status", "unknown")
        plant_id, plant_name = get_plant_info(source, "horticulture")

        # Preserve failed/skipped sources for audit purposes.
        if status != "collected":
            cleaned.append({
                "record_type": "source_status",
                "source_id": source.get("source_id", ""),
                "plant_id": plant_id,
                "plant_name": plant_name,
                "source_url": source.get("url", ""),
                "source_type": "horticulture",
                "collection_status": status,
                "review_status": "needs_manual_review",
            })
            continue

        source_url = source.get("url", "")
        source_id = source.get("source_id", "")
        page_title = source.get("page_title", "")
        excerpts = source.get("excerpts", [])

        for excerpt in excerpts:
            if isinstance(excerpt, dict):
                raw_text = (
                    excerpt.get("text")
                    or excerpt.get("content")
                    or excerpt.get("excerpt")
                    or ""
                )
                heading = excerpt.get("heading", "")
            else:
                raw_text = excerpt
                heading = ""

            text = clean_text(raw_text)

            if not text:
                continue

            cleaned.append({
                "record_type": "excerpt",
                "plant_id": plant_id,
                "plant_name": plant_name,
                "source_id": source_id,
                "source_url": source_url,
                "source_type": "horticulture",
                "page_title": page_title,
                "heading": clean_text(heading),
                "cleaned_text": text,
                "review_status": "needs_manual_review",
            })

            for sentence in split_sentences(text):
                add_candidate(
                    candidates,
                    seen_hashes,
                    sentence,
                    plant_id,
                    plant_name,
                    source_url,
                    "horticulture",
                    source_id=source_id,
                    context=clean_text(heading or page_title),
                )


def main():
    wiki_records = load_json(WIKI_FILE)
    doc_records = load_json(DOCS_FILE)

    cleaned = []
    candidates = []
    seen_hashes = set()

    process_wikipedia(
        wiki_records, candidates, seen_hashes, cleaned
    )
    process_horticulture(
        doc_records, candidates, seen_hashes, cleaned
    )

    KB_DIR.mkdir(parents=True, exist_ok=True)

    CLEAN_FILE.write_text(
        json.dumps(cleaned, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    CANDIDATES_FILE.write_text(
        json.dumps(candidates, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nPREPROCESSING COMPLETE")
    print("-" * 40)
    print("Wikipedia records:", len(wiki_records))
    print("Horticulture records:", len(doc_records))
    print("Cleaned records:", len(cleaned))
    print("Unique candidate facts:", len(candidates))
    print("Output:", CLEAN_FILE)
    print("Output:", CANDIDATES_FILE)
    print("\nAll candidates still require verification.")


if __name__ == "__main__":
    main()
