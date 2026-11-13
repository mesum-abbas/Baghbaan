import pytest

from engine.inference_engine import (
    EXPERT_NOTE,
    MIN_QUESTIONS,
    NONE_OF_THESE,
    NOT_SURE,
    format_report,
    get_plants,
    get_rules,
    get_symptoms,
    load_kb,
    build_tree,
    count_leaves,
    next_step,
    path_to_dot,
    tree_to_dot,
    validate_kb,
    walk_to_rule,
)

ALL_RULES = load_kb()["rules"]


def walk(plant_id, symptom_id, wanted):
    """Answer questions from a dict; anything not in it is answered 'Not sure'."""
    answers = {}
    for _ in range(40):
        step = next_step(plant_id, symptom_id, answers)
        if step["status"] != "ask":
            return step, answers
        qid = step["question"]["id"]
        answers[qid] = wanted.get(qid, NOT_SURE)
    raise AssertionError("consultation did not finish")


# --- knowledge base ---------------------------------------------------------
def test_knowledge_base_is_valid():
    assert validate_kb() == []


@pytest.mark.parametrize("plant", get_plants(), ids=lambda p: p["plant_id"])
def test_each_plant_has_around_40_rules(plant):
    assert 35 <= len(get_rules(plant["plant_id"])) <= 50


def test_every_rule_needs_between_8_and_10_confirmed_answers():
    assert all(MIN_QUESTIONS <= len(r["if"]) <= 10 for r in ALL_RULES)


def test_serious_problems_need_more_evidence_than_mild_ones():
    def count(cid):
        return max(len(r["if"]) for r in ALL_RULES if r["then"] == cid)
    assert count("root_rot") > count("natural_aging")


# --- inference: prune, then confirm -------------------------------------------
@pytest.mark.parametrize("rule", ALL_RULES, ids=lambda r: r["id"])
def test_every_rule_can_be_fully_confirmed(rule):
    step, _ = walk_to_rule(rule)
    assert step["status"] == "diagnosed"
    assert step["diagnosis"]["rule_id"] == rule["id"]
    assert step["diagnosis"]["confirmed"] is True


def test_question_count_is_not_fixed():
    counts = {len(walk_to_rule(r)[1]) for r in ALL_RULES}
    assert min(counts) == MIN_QUESTIONS and max(counts) <= 10
    assert len(counts) >= 3


def test_root_rot_is_only_given_after_enough_signs_are_collected():
    answers = {"how_many": "many", "yellow_type": "whole", "soil": "wet", "smell": "yes"}
    step = next_step("money_plant", "yellow_leaves", answers)
    assert step["status"] == "ask"            # only 4 of 10 signs so far
    step, answers = walk_to_rule(next(r for r in ALL_RULES if r["id"] == "MP02"))
    assert step["diagnosis"]["condition_id"] == "root_rot"
    assert step["diagnosis"]["confirmed"] is True
    assert len(answers) == 10
    assert answers["roots"] == "rotten"


def test_failed_core_sign_never_gives_a_destructive_treatment():
    # Roots are healthy, so Root Rot (cut the roots) must never be suggested.
    answers = {"how_many": "many", "yellow_type": "whole", "soil": "wet", "smell": "yes",
               "roots": "healthy"}
    step, final = walk("money_plant", "yellow_leaves", answers)
    assert step["status"] == "no_match"
    assert len(final) >= MIN_QUESTIONS


def test_wrong_answers_are_pruned_like_a_decision_tree():
    # After "soil is dry", no rule that needs wet soil can ever be asked about again.
    step = next_step("peace_lily", "drooping", {"soil": "dry"})
    assert step["question"]["id"] == "dries_fast"


def test_not_sure_on_confirmation_still_answers_but_is_not_confirmed():
    step, _ = walk("aloe_vera", "pests", {"pests_seen": "cotton"})   # smear -> Not sure
    assert step["status"] == "diagnosed"
    assert step["diagnosis"]["condition_id"] == "mealybugs"
    assert step["diagnosis"]["confirmed"] is False
    assert step["diagnosis"]["expert_note"] != EXPERT_NOTE


def test_not_sure_on_main_question_gives_possibilities():
    step, _ = walk("snake_plant", "pests", {})
    assert step["status"] == "possibilities"
    names = [r["condition_id"] for r in step["results"]]
    assert len(names) == len(set(names)) > 1


def test_none_of_these_ends_in_general_care_after_enough_questions():
    step, answers = walk("money_plant", "pests", {"pests_seen": NONE_OF_THESE})
    assert step["status"] == "no_match"
    assert step["general"]["steps"]
    assert len(answers) >= MIN_QUESTIONS      # information is still collected


def test_missed_support_sign_keeps_asking_and_gives_closest_match():
    rule = next(r for r in ALL_RULES if r["id"] == "MP02")          # root rot
    wanted = {q: v[0] for q, v in rule["if"].items()}
    wanted["water_freq"] = "rare"             # a support sign that does not fit
    step, answers = walk("money_plant", "yellow_leaves", wanted)
    assert step["status"] == "diagnosed"
    assert step["diagnosis"]["condition_id"] == "root_rot"
    assert step["diagnosis"]["closest"] is True
    assert step["diagnosis"]["confirmed"] is False
    assert len(answers) >= MIN_QUESTIONS


def test_yes_no_questions_always_offer_both_answers():
    for plant in get_plants():
        for symptom in get_symptoms(plant["plant_id"]):
            answers = {}
            for _ in range(40):
                step = next_step(plant["plant_id"], symptom["id"], answers)
                if step["status"] != "ask":
                    break
                options = [o["value"] for o in step["question"]["options"]]
                if "yes" in options:
                    assert "no" in options
                answers[step["question"]["id"]] = options[-1]


def test_every_consultation_collects_at_least_7_answers():
    import random
    rng = random.Random(3)
    for plant in get_plants():
        for symptom in get_symptoms(plant["plant_id"]):
            for _ in range(25):
                answers = {}
                while True:
                    step = next_step(plant["plant_id"], symptom["id"], answers)
                    if step["status"] != "ask":
                        break
                    answers[step["question"]["id"]] = rng.choice(step["question"]["options"])["value"]
                assert len(answers) >= MIN_QUESTIONS


def test_only_useful_options_are_offered():
    values = {o["value"] for o in next_step("money_plant", "leaf_spots", {})["question"]["options"]}
    assert "rust" not in values and "wet" in values


def test_symptoms_are_plant_specific():
    aloe = {s["id"] for s in get_symptoms("aloe_vera")}
    lily = {s["id"] for s in get_symptoms("peace_lily")}
    assert "color_change" in aloe and "color_change" not in lily
    assert "flower_problems" in lily and "flower_problems" not in aloe


# --- what the user sees -----------------------------------------------------
def test_result_and_prescription_have_no_percentages():
    rule = next(r for r in ALL_RULES if r["id"] == "PL01")
    step, answers = walk_to_rule(rule)
    report = format_report("peace_lily", "drooping", answers, step)
    assert "Underwatering" in report and "WHAT TO DO" in report
    assert "%" not in report
    assert "confidence" not in str(step["diagnosis"]).lower()


def test_path_diagram_lists_every_answer_and_the_outcome():
    rule = next(r for r in ALL_RULES if r["id"] == "PL01")
    step, answers = walk_to_rule(rule)
    dot = path_to_dot("peace_lily", "drooping", answers, "Underwatering")
    assert dot.startswith("digraph")
    assert dot.count("fillcolor=\"#ffffff\"") == len(answers)     # one box per question
    assert "Underwatering" in dot and "left)" in dot


def test_every_plant_has_a_photo_and_credit():
    import json
    from pathlib import Path
    assets = Path(__file__).resolve().parent.parent / "assets" / "plants"
    credits = json.loads((assets / "credits.json").read_text(encoding="utf-8"))
    for plant in get_plants():
        assert (assets / f"{plant['plant_id']}.jpg").exists()
        assert credits[plant["plant_id"]]["license"]


def test_decision_tree_shows_only_splitting_questions_and_stays_small():
    tree = build_tree("money_plant", "yellow_leaves")
    dot = tree_to_dot(tree, {"how_many": "many", "yellow_type": "whole"})
    boxes = [l for l in dot.splitlines() if "[label=" in l and "->" not in l]
    assert len(boxes) < 3 * count_leaves(tree)            # no long chains of confirming questions
    assert "confirming questions" in dot                  # leaves say how many follow
    assert "#1f7a4a" in dot                               # the user's path is highlighted
    assert not any(l.startswith("+") for l in dot.splitlines())   # labels stay on one DOT line
