"""
Plant Care Expert - rule-based inference engine.

How it works
------------
The knowledge base holds IF-THEN rules, about 40 per plant, for example:

    IF   plant = Money Plant AND symptom = Yellow leaves
    AND  how many = several AND soil = wet AND smell = sour
    THEN Root Rot

Each problem also has confirmation signs (conditions.json -> "confirm"),
for Root Rot: "roots are brown and mushy". These are added to every rule that
points to that problem, so a rule only fires when its problem is confirmed.

For a chosen plant and symptom, every rule is a candidate (hypothesis):

  1. Ask the question that best splits the remaining candidates.
  2. Prune every rule that contradicts the answer, like cutting branches
     of a decision tree.
  3. When one rule is left, ask its remaining conditions to confirm it.
  4. Stop when exactly one rule is left with ALL its conditions confirmed.
     The machine is then fully sure of that rule, and the user gets the
     problem and its prescription.

There is no fixed number of questions. It depends on how fast the other
problems are pruned and how many signs the last one needs. The user never
sees a percentage. They see the problem, what to do, and a short reminder
to let a plant expert check it, because a program cannot replace one.
"""

import json
import textwrap
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "knowledge_base"

NOT_SURE = "not_sure"
NONE_OF_THESE = "none_of_these"
MIN_QUESTIONS = 8     # every consultation asks, and every diagnosis rests on, at least this many answers
# Serious problems need more evidence before the engine names them.
SEVERITY_TARGET = {"low": 8, "medium": 9, "high": 10}

YES_NO = [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]
SPECIAL_LABELS = {NOT_SURE: "Not sure", NONE_OF_THESE: "None of these"}

# Core signs (the rule's own path and the problem's confirmation signs) must
# match. Support signs may miss up to this many times; the engine then keeps
# asking and reports the closest match instead of stopping with no answer.
MAX_SOFT_MISMATCH = 2
HARD = 99

EXPERT_NOTE_CLOSEST = ("This is the closest match to your answers. Some of the usual signs did not fit, "
                       "so please let a nursery or plant expert confirm it before you treat the plant.")
# Terminal node for a branch that matches no rule. Before reaching it the engine
# still asks these general questions until MIN_QUESTIONS answers are collected.
GENERAL_QUESTIONS = ["soil", "water_freq", "light", "new_growth", "smell", "stem_base",
                     "sticky", "temp", "neighbors", "dry_air", "moved", "fertilizer"]
GENERAL_CARE = {
    "name": "No specific problem matched yet",
    "about": ("Your answers do not match one single problem this program knows. That is common when a plant "
              "has more than one small stress at the same time. Start with these safe checks, and let a "
              "plant expert look at it."),
    "steps": [
        "Check the soil 2-3 cm deep. Water only if it is dry (snake plant and aloe: only if it is dry all the way down). Do not water on a fixed schedule.",
        "Make sure the pot has a drainage hole and that no water is left standing in the saucer.",
        "Move the plant to bright, indirect light, away from AC vents, heaters, cold drafts and hot window glass.",
        "Look under the leaves, along the stems and on the soil for insects, webbing or sticky residue. If you find any, keep the plant away from other plants.",
        "Remove only leaves that are completely dry or dead, using clean scissors.",
        "Take clear photos of the whole plant, the affected leaves, the soil and the roots, and show them to a nursery or plant expert.",
    ],
    "avoid": ["Do not fertilize, repot, or spray any chemical or fungicide until the cause is known.",
              "Do not change many things at once. Change one thing and watch for a week."],
    "prevent": ["Check the soil before every watering.", "Keep a steady routine with bright, indirect light and no standing water."],
}

EXPERT_NOTE = ("Before using any chemical, cutting roots or throwing the plant away, "
               "show it to a nursery or plant expert.")
EXPERT_NOTE_UNCONFIRMED = ("Some signs could not be checked, so please let a nursery "
                           "or plant expert confirm this before you treat the plant.")


# ---------------------------------------------------------------------------
# Knowledge base loading
# ---------------------------------------------------------------------------
def _read_json(path):
    with Path(path).open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _as_list(value):
    return value if isinstance(value, list) else [value]


@lru_cache(maxsize=1)
def load_kb():
    """Load the whole knowledge base (cached) and build the full rules."""
    plants = _read_json(KB_DIR / "plants.json")
    symptoms = _read_json(KB_DIR / "symptoms.json")["symptoms"]
    conditions = _read_json(KB_DIR / "conditions.json")["conditions"]
    sources = {s["source_id"]: s for s in _read_json(KB_DIR / "sources.json")}

    questions = {}
    for raw in _read_json(KB_DIR / "questions.json")["questions"]:
        question = dict(raw)
        if question["options"] == "yes_no":
            question["options"] = YES_NO
        questions[question["id"]] = question

    rules = []
    for path in sorted((KB_DIR / "rules").glob("*.json")):
        data = _read_json(path)
        for raw in data["rules"]:
            rule = dict(raw)
            rule["plant_id"] = data["plant_id"]
            # The rule's own conditions (the decision-tree path) ...
            conds = {qid: _as_list(v) for qid, v in raw["if"].items()}
            # ... plus the problem's confirmation signs. If both mention the
            # same question, the rule's own value wins.
            condition = conditions.get(raw["then"], {})
            confirm = condition.get("confirm", {})
            rule["confirm_questions"] = [q for q in confirm if q not in conds]
            for qid in rule["confirm_questions"]:
                conds[qid] = _as_list(confirm[qid])
            # Support signs (more history / "no other cause" checks) are added
            # in order until the rule needs MIN_QUESTIONS answers, so every
            # diagnosis rests on enough collected information.
            target = SEVERITY_TARGET.get(condition.get("severity"), MIN_QUESTIONS)
            rule["support_questions"] = []
            for qid, values in condition.get("support", {}).items():
                if len(conds) >= target:
                    break
                if qid not in conds:
                    conds[qid] = _as_list(values)
                    rule["support_questions"].append(qid)
            rule["if"] = conds
            rules.append(rule)

    return {
        "plants": plants,
        "symptoms": symptoms,
        "conditions": conditions,
        "sources": sources,
        "questions": questions,
        "question_order": list(questions),
        "rules": rules,
    }


def get_plants():
    return load_kb()["plants"]


def get_plant(plant_id):
    return next((p for p in get_plants() if p["plant_id"] == plant_id), None)


def get_question(question_id):
    return load_kb()["questions"].get(question_id)


def get_condition(condition_id):
    return load_kb()["conditions"].get(condition_id)


def get_rules(plant_id, symptom_id=None):
    return [
        r for r in load_kb()["rules"]
        if r["plant_id"] == plant_id and (symptom_id is None or r["symptom"] == symptom_id)
    ]


def get_symptoms(plant_id):
    """Symptoms that have at least one rule for this plant, in a fixed order."""
    used = {r["symptom"] for r in get_rules(plant_id)}
    return [s for s in load_kb()["symptoms"] if s["id"] in used]


def get_symptom(symptom_id):
    return next((s for s in load_kb()["symptoms"] if s["id"] == symptom_id), None)


def answer_label(question_id, value):
    if value in SPECIAL_LABELS:
        return SPECIAL_LABELS[value]
    question = get_question(question_id)
    for option in question["options"] if question else []:
        if option["value"] == value:
            return option["label"]
    return str(value)


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------
def _is_consistent(rule, answers):
    """A rule survives (is not pruned) unless an answer contradicts it."""
    for qid, accepted in rule["if"].items():
        answer = answers.get(qid)
        if answer is None or answer == NOT_SURE:
            continue
        if answer not in accepted:
            return False
    return True


def candidate_rules(plant_id, symptom_id, answers):
    """Strict candidates: rules with no contradicting answer at all."""
    return [r for r in get_rules(plant_id, symptom_id) if _is_consistent(r, answers)]


def soft_mismatches(rule, answers):
    """
    Number of support signs that contradict the answers. A contradicted core sign
    (path or confirmation), or "None of these", returns HARD and rules the rule out.
    """
    misses = 0
    for qid, accepted in rule["if"].items():
        answer = answers.get(qid)
        if answer is None or answer == NOT_SURE or answer in accepted:
            continue
        if answer == NONE_OF_THESE or qid not in rule["support_questions"]:
            return HARD
        misses += 1
    return misses if misses <= MAX_SOFT_MISMATCH else HARD


def closest_rules(plant_id, symptom_id, answers):
    """(fewest mismatches, rules that have exactly that many). (None, []) if all are ruled out."""
    scored = [(soft_mismatches(r, answers), r) for r in get_rules(plant_id, symptom_id)]
    scored = [(m, r) for m, r in scored if m < HARD]
    if not scored:
        return None, []
    best = min(m for m, _ in scored)
    return best, [r for m, r in scored if m == best]


def _pick_question(candidates, answers):
    """
    Choose the next question:
    1. prefer questions that split (prune) the candidates,
    2. then questions mentioned by more candidates,
    3. then the order in questions.json.
    Once one candidate is left, this returns its unchecked conditions, which
    are the confirmation questions. Returns None when nothing is left to ask.
    """
    order = load_kb()["question_order"]
    unanswered = {qid for r in candidates for qid in r["if"] if qid not in answers}
    if not unanswered:
        return None

    def score(qid):
        mentioning = [r for r in candidates if qid in r["if"]]
        value_sets = {tuple(sorted(r["if"][qid])) for r in mentioning}
        splits = len(value_sets) > 1 or len(mentioning) < len(candidates)
        return (splits, len(mentioning), -order.index(qid))

    return max(unanswered, key=score)


def _options_for(question_id, candidates):
    """Answers at least one of these rules can use (used for the decision tree)."""
    question = get_question(question_id)
    return [
        option for option in question["options"]
        if any(_is_consistent(r, {question_id: option["value"]}) for r in candidates)
    ]


def _options_to_show(question_id, plant_id, symptom_id):
    """
    Answers shown to the user. Yes/No questions always show both, so the user can
    answer truthfully. Other questions hide answers that no rule of this plant and
    symptom uses (for example "orange rust spots" for a Money Plant).
    """
    question = get_question(question_id)
    if question["options"] == YES_NO:
        return list(YES_NO)
    group = get_rules(plant_id, symptom_id)
    used = [o for o in question["options"] if any(o["value"] in r["if"].get(question_id, []) for r in group)]
    return used or list(question["options"])


def build_result(rule, answers):
    """Turn a fired rule into the problem and its prescription."""
    unsure = [qid for qid in rule["if"] if answers.get(qid) == NOT_SURE]
    confirmed = sum(1 for qid, ok in rule["if"].items() if answers.get(qid) in ok)
    fully_confirmed = not unsure and confirmed == len(rule["if"])
    missed = len(rule["if"]) - confirmed - len(unsure)
    return {
        "rule_id": rule["id"],
        "plant_id": rule["plant_id"],
        "symptom": rule["symptom"],
        "condition_id": rule["then"],
        "condition": get_condition(rule["then"]),
        "note": rule.get("note", ""),
        "confirmed": fully_confirmed,        # internal: machine is fully sure
        "signs_confirmed": confirmed,        # internal: used for ranking
        "signs_total": len(rule["if"]),
        "closest": missed > 0,               # some support signs did not fit
        "signs_missed": missed,
        "expert_note": (EXPERT_NOTE if fully_confirmed
                        else EXPERT_NOTE_CLOSEST if missed else EXPERT_NOTE_UNCONFIRMED),
    }


def next_step(plant_id, symptom_id, answers=None):
    """
    Main entry point. Given the answers so far, returns one of:
      {"status": "ask", "question": {...}}
      {"status": "diagnosed", "diagnosis": result}   one rule left
      {"status": "possibilities", "results": [...]}  "Not sure" answers kept several
      {"status": "no_match"}                         every rule was pruned
    """
    answers = answers or {}
    # Rules with no contradiction come first. If a support sign did not fit, the
    # rules with the fewest misses stay in play and the engine keeps asking until
    # it reaches the end of that branch (a terminal node).
    _, candidates = closest_rules(plant_id, symptom_id, answers)

    if not candidates:
        # Dead end: no rule fits. Keep collecting general information first.
        if len(answers) < MIN_QUESTIONS:
            general = next((q for q in GENERAL_QUESTIONS if q not in answers), None)
            if general:
                question = dict(get_question(general))
                question["options"] = _options_to_show(general, plant_id, symptom_id)
                return {"status": "ask", "question": question}
        return {"status": "no_match", "general": GENERAL_CARE}

    question_id = _pick_question(candidates, answers)
    if question_id:
        question = dict(get_question(question_id))
        question["options"] = _options_to_show(question_id, plant_id, symptom_id)
        return {"status": "ask", "question": question}

    results = [build_result(r, answers) for r in candidates]
    if len(results) == 1:
        return {"status": "diagnosed", "diagnosis": results[0]}

    # Several rules survived because of "Not sure" answers: best supported first,
    # and each problem listed once.
    results.sort(key=lambda res: (res["signs_confirmed"], -res["signs_total"]), reverse=True)
    unique, seen = [], set()
    for res in results:
        if res["condition_id"] not in seen:
            seen.add(res["condition_id"])
            unique.append(res)
    if len(unique) == 1:
        return {"status": "diagnosed", "diagnosis": unique[0]}
    return {"status": "possibilities", "results": unique}


# ---------------------------------------------------------------------------
# How every condition was checked (for the "conditions checked" table)
# ---------------------------------------------------------------------------
def conditions_checked(plant_id, symptom_id, answers):
    """
    One row per rule of this plant, showing what happened to it:
      confirmed / possible (still alive) / ruled_out (pruned by an answer) /
      other_symptom (belongs to a symptom the user did not choose).
    """
    group = get_rules(plant_id, symptom_id)
    best, alive_rules = closest_rules(plant_id, symptom_id, answers)
    alive = {r["id"] for r in alive_rules}
    pruned = {}
    asked = [(qid, v) for qid, v in answers.items()]
    for number, (qid, value) in enumerate(asked, 1):
        if value == NOT_SURE:
            continue
        for rule in group:
            if rule["id"] not in pruned and qid in rule["if"] and value not in rule["if"][qid]:
                pruned[rule["id"]] = (number, qid, value)

    rows = []
    for rule in get_rules(plant_id):
        name = get_condition(rule["then"])["name"]
        symptom = get_symptom(rule["symptom"])["name"]
        if rule["symptom"] != symptom_id:
            rows.append({"order": (3, 0), "rule_id": rule["id"], "problem": name,
                         "state": "other_symptom", "why": f"Belongs to '{symptom}', not the symptom you chose"})
        elif rule["id"] in alive and best:
            rows.append({"order": (0, 0), "rule_id": rule["id"], "problem": name,
                         "state": "closest",
                         "why": f"Closest match: {best} supporting sign(s) did not fit, but its main signs did"})
        elif rule["id"] in alive:
            confirmed = len(alive) == 1 and all(answers.get(q) in ok for q, ok in rule["if"].items())
            rows.append({"order": (0, 0), "rule_id": rule["id"], "problem": name,
                         "state": "confirmed" if confirmed else "possible",
                         "why": "All its signs matched your answers" if confirmed
                                else "No answer has ruled it out yet"})
        else:
            number, qid, value = pruned.get(rule["id"], (0, None, None))
            if qid is None:
                rows.append({"order": (1, 0), "rule_id": rule["id"], "problem": name,
                             "state": "ruled_out", "question_no": 0,
                             "why": "A closer-matching condition was found"})
                continue
            rows.append({"order": (1, number), "rule_id": rule["id"], "problem": name,
                         "state": "ruled_out", "question_no": number,
                         "why": f"{get_question(qid)['text']} -> {answer_label(qid, value)}"})
    rows.sort(key=lambda r: r["order"])
    return rows


# ---------------------------------------------------------------------------
# Decision tree diagram
# ---------------------------------------------------------------------------
def build_tree(plant_id, symptom_id):
    """Build the full decision tree for one plant and symptom from its rules."""
    return _grow(get_rules(plant_id, symptom_id), {})


def _grow(candidates, answers):
    if not candidates:
        return {"type": "none"}
    question_id = _pick_question(candidates, answers)
    if question_id is None:
        return {"type": "leaf", "rule": candidates[0]}
    # Answers that leave exactly the same rules share one branch.
    branches = {}
    for option in _options_for(question_id, candidates):
        branch = [r for r in candidates if _is_consistent(r, {question_id: option["value"]})]
        key = tuple(r["id"] for r in branch)
        branches.setdefault(key, ([], branch))[0].append(option)
    children = []
    for options, branch in branches.values():
        child = _grow(branch, {**answers, question_id: options[0]["value"]})
        children.append((options, child))
    return {"type": "question", "question_id": question_id, "children": children}


def count_leaves(tree):
    if tree["type"] != "question":
        return 1 if tree["type"] == "leaf" else 0
    return sum(count_leaves(child) for _, child in tree["children"])


def _wrap(text, width=26):
    return "\\n".join(textwrap.wrap(text.replace('"', "'"), width))


def tree_to_dot(tree, answers=None):
    """
    Graphviz DOT text for the decision tree. Only questions that split the possibilities
    are drawn; each end node (a problem) says how many confirming questions still follow.
    The user's own path is highlighted in green.
    """
    answers = answers or {}
    lines = [
        "digraph G {",
        '  rankdir=LR; bgcolor="transparent"; nodesep=0.3; ranksep=0.7;',
        '  node [fontname="Helvetica", fontsize=14, style="rounded,filled", shape=box, margin="0.15,0.1"];',
        '  edge [fontname="Helvetica", fontsize=12];',
    ]
    counter = [0]

    def visit(node, on_path, depth):
        # A question with one possible branch splits nothing: it is a confirming question.
        while node["type"] == "question" and len(node["children"]) == 1:
            options, child = node["children"][0]
            given = answers.get(node["question_id"])
            if given is not None and given != NOT_SURE and given not in {o["value"] for o in options}:
                on_path = False
            node = child
        counter[0] += 1
        node_id = f"n{counter[0]}"
        border = "#1f7a4a" if on_path else "#9aa59d"
        width = "2.5" if on_path else "1"
        if node["type"] == "question":
            text = get_question(node["question_id"])["text"]
            fill = "#e6f4ea" if on_path else "#ffffff"
            lines.append(f'  {node_id} [label="{_wrap(text)}", fillcolor="{fill}", color="{border}", penwidth={width}];')
            for options, child in node["children"]:
                values = {o["value"] for o in options}
                child_on_path = on_path and answers.get(node["question_id"]) in values
                child_id = visit(child, child_on_path, depth + 1)
                colour = "#1f7a4a" if child_on_path else "#b5beb7"
                pen = "2.5" if child_on_path else "1"
                edge_label = "\\nor ".join(_wrap(o["label"], 22) for o in options)
                lines.append(f'  {node_id} -> {child_id} [label="{edge_label}", color="{colour}", fontcolor="{colour}", penwidth={pen}];')
        elif node["type"] == "leaf":
            rule = node["rule"]
            name = get_condition(rule["then"])["name"]
            fill = "#1f7a4a" if on_path else "#f3f6f3"
            font = "#ffffff" if on_path else "#1b2a21"
            extra = len(rule["if"]) - depth
            more = f"\\n+{extra} confirming questions" if extra > 0 else ""
            lines.append(f'  {node_id} [label="{_wrap(name)}{more}", fillcolor="{fill}", fontcolor="{font}", color="{border}", penwidth={width}];')
        else:
            lines.append(f'  {node_id} [label="No rule\\n(ask an expert)", fillcolor="#fff4e5", color="#d9822b"];')
        return node_id

    visit(tree, True, 0)
    lines.append("}")
    return "\n".join(lines)


def path_to_dot(plant_id, symptom_id, answers, outcome=None):
    """
    Readable top-to-bottom diagram of the user's own path: each question, the answer
    given, and how many conditions were still possible after it. `outcome` is the
    final problem name (None while the consultation is still running).
    """
    total = len(get_rules(plant_id, symptom_id))
    lines = [
        "digraph P {",
        '  rankdir=TB; bgcolor="transparent"; nodesep=0.25; ranksep=0.35;',
        '  node [fontname="Helvetica", fontsize=11, style="rounded,filled", shape=box, margin="0.18,0.10"];',
        '  edge [color="#1f7a4a", penwidth=1.6, arrowsize=0.7];',
        f'  s [label="{_wrap(get_symptom(symptom_id)["name"], 34)}\\n{total} conditions possible", '
        'fillcolor="#e6f4ea", color="#1f7a4a"];',
    ]
    previous, so_far = "s", {}
    for number, (qid, value) in enumerate(answers.items(), 1):
        so_far[qid] = value
        _, remaining = closest_rules(plant_id, symptom_id, so_far)
        left = f"{len(remaining)} left" if remaining else "none left"
        label = f"{number}. {_wrap(get_question(qid)['text'], 34)}\\n-> {_wrap(answer_label(qid, value), 34)}\\n({left})"
        lines.append(f'  q{number} [label="{label}", fillcolor="#ffffff", color="#9aa59d"];')
        lines.append(f"  {previous} -> q{number};")
        previous = f"q{number}"
    if outcome:
        lines.append(f'  end [label="{_wrap(outcome, 30)}", fillcolor="#1f7a4a", fontcolor="#ffffff", '
                     'color="#14573a", fontsize=13];')
        lines.append(f"  {previous} -> end;")
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prescription text (download / print)
# ---------------------------------------------------------------------------
def _prescription_lines(result, plant):
    cond = result["condition"]
    lines = [f"PROBLEM: {cond['name']}", "", cond["about"]]
    if result["note"]:
        lines += ["", f"{plant['common_name']} note: {result['note']}"]
    lines += ["", "WHAT TO DO:"] + [f"  {i}. {s}" for i, s in enumerate(cond["steps"], 1)]
    lines += ["", "AVOID:"] + [f"  - {a}" for a in cond["avoid"]]
    lines += ["", "PREVENT IT NEXT TIME:"] + [f"  - {p}" for p in cond["prevent"]]
    return lines


def format_report(plant_id, symptom_id, answers, step):
    plant = get_plant(plant_id)
    symptom = get_symptom(symptom_id)
    lines = [
        "PLANT CARE EXPERT - PRESCRIPTION",
        "=" * 40,
        f"Plant  : {plant['common_name']} ({plant['scientific_name']})",
        f"Problem seen: {symptom['name']}",
        "",
    ]
    if step["status"] == "diagnosed":
        lines += _prescription_lines(step["diagnosis"], plant)
        lines += ["", "NOTE: " + step["diagnosis"]["expert_note"]]
    elif step["status"] == "possibilities":
        lines.append("It could be one of these problems:")
        for res in step["results"]:
            lines += [""] + _prescription_lines(res, plant)
        lines += ["", "NOTE: " + EXPERT_NOTE_UNCONFIRMED]
    else:
        general = GENERAL_CARE
        lines += [f"PROBLEM: {general['name']}", "", general["about"], "", "WHAT TO DO:"]
        lines += [f"  {i}. {s}" for i, s in enumerate(general["steps"], 1)]
        lines += ["", "AVOID:"] + [f"  - {a}" for a in general["avoid"]]
        lines += ["", "NOTE: Please show the plant to a nursery or plant expert."]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Knowledge base validation (used by scripts/validate_kb.py and the tests)
# ---------------------------------------------------------------------------
def _check_values(errors, where, kb, qid, values):
    question = kb["questions"].get(qid)
    if not question:
        errors.append(f"{where}: unknown question '{qid}'")
        return
    valid = {o["value"] for o in question["options"]}
    for value in _as_list(values):
        if value not in valid:
            errors.append(f"{where}: '{value}' is not an option of question '{qid}'")


def validate_kb():
    """Return a list of problems found in the knowledge base (empty = valid)."""
    kb = load_kb()
    errors = []
    plant_ids = {p["plant_id"] for p in kb["plants"]}
    symptom_ids = {s["id"] for s in kb["symptoms"]}
    seen_ids = set()

    for rule in kb["rules"]:
        rid = rule["id"]
        if rid in seen_ids:
            errors.append(f"{rid}: duplicate rule id")
        seen_ids.add(rid)
        if rule["plant_id"] not in plant_ids:
            errors.append(f"{rid}: unknown plant '{rule['plant_id']}'")
        if rule["symptom"] not in symptom_ids:
            errors.append(f"{rid}: unknown symptom '{rule['symptom']}'")
        if rule["then"] not in kb["conditions"]:
            errors.append(f"{rid}: unknown condition '{rule['then']}'")
        for qid, values in rule["if"].items():
            _check_values(errors, rid, kb, qid, values)

    for rule in kb["rules"]:
        if len(rule["if"]) < MIN_QUESTIONS:
            errors.append(f"{rule['id']}: only {len(rule['if'])} signs, needs {MIN_QUESTIONS} "
                          f"(add more 'support' signs to condition '{rule['then']}')")

    for cid, cond in kb["conditions"].items():
        if not cond.get("confirm"):
            errors.append(f"condition {cid}: has no confirmation signs")
        for key in ("confirm", "support"):
            for qid, values in cond.get(key, {}).items():
                _check_values(errors, f"condition {cid} {key}", kb, qid, values)
        for sid in cond.get("sources", []):
            if sid not in kb["sources"]:
                errors.append(f"condition {cid}: unknown source '{sid}'")

    # Decision-tree property: two rules for the same plant and symptom must
    # disagree on at least one shared question, so one set of answers can
    # never confirm both.
    groups = {}
    for rule in kb["rules"]:
        groups.setdefault((rule["plant_id"], rule["symptom"]), []).append(rule)
    for group in groups.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                shared = set(a["if"]) & set(b["if"])
                if not any(not set(a["if"][q]) & set(b["if"][q]) for q in shared):
                    errors.append(f"{a['id']} and {b['id']}: can both fire on the same answers")

    return errors


def walk_to_rule(rule, max_questions=40):
    """
    Simulate a user whose plant really has this rule's problem: answer each
    question the way the rule expects. If a question is not part of this rule,
    pick the answer that prunes the most other rules. Returns (step, answers).
    """
    answers = {}
    for _ in range(max_questions):
        step = next_step(rule["plant_id"], rule["symptom"], answers)
        if step["status"] != "ask":
            return step, answers
        qid = step["question"]["id"]
        if qid in rule["if"]:
            answers[qid] = rule["if"][qid][0]
        else:
            others = candidate_rules(rule["plant_id"], rule["symptom"], answers)
            answers[qid] = min(
                (o["value"] for o in step["question"]["options"]),
                key=lambda v: sum(_is_consistent(r, {qid: v}) for r in others),
            )
    return {"status": "loop"}, answers
