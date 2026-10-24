
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_FILE = ROOT / "knowledge_base" / "diagnostic_rules.json"


def load_rules():
    """Load diagnostic rules from the JSON knowledge base."""
    if not RULES_FILE.exists():
        raise FileNotFoundError(
            f"Rules file not found: {RULES_FILE}"
        )

    with RULES_FILE.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)

    return data.get("rules", [])


def diagnose(plant_id, symptom, answers=None):
    """
    Rank approved rules using the user's answers.

    answers example:
    {
        "soil_stays_wet": True,
        "pot_has_poor_drainage": False
    }

    Only reviewed and approved rules are returned.
    """
    answers = answers or {}
    rules = load_rules()
    results = []

    for rule in rules:

        # Never use unapproved or unreviewed rules
        if not rule.get("approved", False):
            continue

        if not rule.get("evidence_reviewed", False):
            continue

        # Match the selected plant and symptom
        if rule.get("plant_id") != plant_id:
            continue

        if rule.get("symptom") != symptom:
            continue

        indicators = rule.get("indicators", [])

        # Consider only indicators the user has answered
        known_indicators = [
            indicator for indicator in indicators
            if indicator in answers
            and isinstance(answers[indicator], bool)
        ]

        matched_indicators = [
            indicator for indicator in known_indicators
            if answers[indicator] is True
        ]

        # Do not treat missing answers as negative evidence
        if known_indicators:
            score = round(
                len(matched_indicators) / len(known_indicators) * 100
            )
        else:
            score = None

        results.append({
            "rule_id": rule["rule_id"],
            "possible_cause": rule["possible_cause"],
            "evidence_score_percent": score,
            "matched_indicators": matched_indicators,
            "indicators_to_check": [
                indicator for indicator in indicators
                if indicator not in answers
            ],
            "recommended_action": rule["recommended_action"],
            "confidence": rule.get("confidence", "low"),
            "safety_note": rule.get("safety_note", ""),
            "source_ids": rule.get("source_ids", [])
        })

    # Rank rules with stronger matching evidence first.
    # A missing score means there is not enough evidence yet.
    results.sort(
        key=lambda result: (
            result["evidence_score_percent"] is not None,
            result["evidence_score_percent"]
            if result["evidence_score_percent"] is not None
            else -1
        ),
        reverse=True
    )

    return results


if __name__ == "__main__":
    # Test case: Money Plant with yellow leaves
    sample_answers = {
        "soil_stays_wet": True,
        "pot_has_poor_drainage": False
    }

    try:
        matches = diagnose(
            "money_plant",
            "yellow_leaves",
            sample_answers
        )

        if matches:
            print(json.dumps(
                matches,
                indent=2,
                ensure_ascii=False
            ))
        else:
            print("No approved diagnostic rule found.")
            print(
                "Review and approve evidence-backed rules "
                "before using them."
            )

    except (FileNotFoundError, json.JSONDecodeError) as error:
        print(f"Knowledge base error: {error}")
