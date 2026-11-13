"""
Check the knowledge base and print a summary.

    python scripts/validate_kb.py

Checks: every rule and confirmation sign refers to a real plant, symptom,
problem, question and answer; no two rules can fire on the same answers; and
every rule can be fully confirmed by answering its own questions.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.inference_engine import (  # noqa: E402
    get_plants, get_rules, get_symptoms, load_kb, validate_kb, walk_to_rule,
)


def main():
    kb = load_kb()
    errors = validate_kb()

    print("=== PLANT CARE EXPERT - KNOWLEDGE BASE CHECK ===")
    print(f"Questions: {len(kb['questions'])}   Problems: {len(kb['conditions'])}   Rules: {len(kb['rules'])}\n")

    for plant in get_plants():
        print(f"{plant['common_name']:<13} {len(get_rules(plant['plant_id'])):>3} rules")
        for symptom in get_symptoms(plant["plant_id"]):
            group = get_rules(plant["plant_id"], symptom["id"])
            counts = []
            for rule in group:
                step, answers = walk_to_rule(rule)
                ok = (step["status"] == "diagnosed"
                      and step["diagnosis"]["rule_id"] == rule["id"]
                      and step["diagnosis"]["confirmed"])
                if not ok:
                    errors.append(f"{rule['id']}: cannot be fully confirmed ({step['status']})")
                counts.append(len(answers))
            print(f"    {symptom['name']:<36} {len(group):>2} rules, "
                  f"{min(counts)}-{max(counts)} questions to confirm")

    used = Counter(r["then"] for r in kb["rules"])
    unused = sorted(set(kb["conditions"]) - set(used))
    if unused:
        print(f"\nProblems not used by any rule: {', '.join(unused)}")

    if errors:
        print(f"\nFOUND {len(errors)} PROBLEM(S):")
        for err in errors:
            print("  -", err)
        sys.exit(1)
    print("\nKnowledge base is valid.")


if __name__ == "__main__":
    main()
