# Plant Care Expert

A rule-based **expert system** that finds the problem with 5 common houseplants
and gives a prescription. It asks simple questions, prunes the problems that
don't fit (like a decision tree), and only answers when the remaining problem is
**fully confirmed**.

The user sees only what is useful: **the problem, what to do, what to avoid,
and how to prevent it**, plus a short reminder to let a plant expert check it.
A program cannot replace an expert.

## Plants and rules

| Plant | Scientific name | Rules |
| :--- | :--- | :---: |
| Money Plant (Golden Pothos) | *Epipremnum aureum* | 46 |
| Snake Plant | *Dracaena trifasciata* | 42 |
| Aloe Vera | *Aloe vera* | 41 |
| Spider Plant | *Chlorophytum comosum* | 43 |
| Peace Lily | *Spathiphyllum wallisii* | 45 |

Together: **217 rules** covering **43 real problems**. These include root rot,
bacterial soft rot, southern blight, red leaf spot, aloe rust, aloe mite, spider
mites, mealybugs, scale, fungus gnats, nutrient deficiencies, fluoride burn, sun
scorch, cold damage, and normal causes such as old-leaf aging and winter rest.

## How the inference engine works

### 1. Rules, confirmation signs and support signs
Each rule is an IF-THEN path for one plant and symptom:

```json
{"id": "MP02", "symptom": "yellow_leaves",
 "if": {"how_many": "many", "yellow_type": ["whole", "pale"], "soil": "wet", "smell": "yes"},
 "then": "root_rot"}
```

Each problem in `conditions.json` adds more signs to every rule that points to it:

```json
"root_rot": {
  "severity": "high",
  "confirm": {"roots": "rotten"},
  "support": {"soil_wet_days": "yes", "water_freq": ["often", "normal"], "leaf_feel": "soft", ...}
}
```

* **path** = the rule's own `if` (how the tree reaches it)
* **confirm** = core signs of the problem (for Root Rot: the roots are rotten)
* **support** = history and "no other cause" checks (watering habit, new growth,
  no insects...), added in order until the rule has enough signs

### 2. Prune, then confirm
1. The user picks a plant and the main symptom. Every rule for that pair is a candidate.
2. The engine asks the question that best **splits** the remaining candidates.
3. Every rule that contradicts the answer is **pruned**.
4. When one rule is left, the engine keeps asking its remaining signs.
5. The answer is given only when **exactly one rule is left and all of its
   signs are confirmed**.

**Every consultation asks at least 8 questions, and a diagnosis rests on 8 to 10.**
How many depends on the problem: mild problems need 8, medium 9, serious ones
(root rot, bacterial disease, soft rot, aloe mite) 10, because a wrong
diagnosis of those costs more.

**Core signs vs support signs**
* **Core signs** (the rule's own path and the problem's `confirm` signs) must
  match. If one is contradicted, that problem is dropped. This is why a plant
  with healthy roots is never told to have its roots cut for root rot.
* **Support signs** (history and "no other cause" checks) may miss up to 2 times.
  The engine keeps asking and gives the **closest match** with a stronger
  "let an expert confirm" note, instead of stopping with no answer.
* Every Yes/No question always offers both **Yes** and **No**.

**No dead ends.** If an answer path matches no rule, the engine keeps collecting
general information (soil, watering, light, new growth, smell...) until it has
8 answers, then ends at a safe **General care** node: check the soil, drainage
and light, look for insects, and show the plant to an expert. It never
suggests cutting roots or spraying chemicals there.

### 3. Possible outcomes
| Outcome | When | What the user sees |
| :--- | :--- | :--- |
| Confirmed | One rule left, all 8-10 signs matched | Problem + prescription + "show it to an expert before chemicals" |
| Closest match | Core signs matched, a support sign did not | Same prescription + "closest match, please let an expert confirm" |
| Not fully confirmed | Some answers were "Not sure" | Same prescription + "please let an expert confirm first" |
| A few possibilities | "Not sure" kept several problems open | The possible problems, each with its prescription |
| General care | A core sign contradicted every rule | Safe general checks + "show it to an expert" |

No percentages are shown. The prescription can be downloaded as a text file. The
result page also shows the **decision tree** (only the questions that split the
possibilities, with the user's path in green, zoomable), **Your path** (each question,
the answer, and how many conditions were still possible), and a table of how every
condition was checked. The tree viewer loads viz.js from a CDN; a compact
Streamlit chart is provided as an offline fallback.

Within one plant and symptom, any two rules must disagree on at least one
shared question, so one set of answers can never confirm two problems. The
validator checks this.

## Project structure

```text
Plant Care Expert/
├── streamlit_app.py            # Web interface (plant photos, stepper, prescription cards)
├── assets/plants/              # 5 plant photos (Wikimedia Commons) + credits.json
├── engine/
│   └── inference_engine.py     # Pruning + confirmation inference, prescription text, KB validation
├── knowledge_base/
│   ├── plants.json             # 5 plants
│   ├── symptoms.json           # Symptom list
│   ├── questions.json          # 61 questions (English + Roman Urdu)
│   ├── conditions.json         # 43 problems: confirm + support signs, what to do, avoid, prevent
│   ├── sources.json            # Extension-service references
│   └── rules/                  # One file of IF-THEN rules per plant
├── scripts/
│   └── validate_kb.py          # Knowledge base check and summary
└── tests/
    └── test_inference_engine.py
```

## Run

```powershell
cd "C:\Users\Mesam\Desktop\learning\Plant Care Expert"
.venv\Scripts\activate
pip install -r requirements.txt

streamlit run streamlit_app.py      # web app -> http://localhost:8501
python scripts/validate_kb.py       # check the knowledge base
pytest -q                           # run the tests
```

## Adding a rule or a problem
1. Add the rule to `knowledge_base/rules/<plant>.json`. Use question ids from
   `questions.json` and a problem id from `conditions.json`.
2. For a new problem, add it to `conditions.json` with at least one `confirm` sign and enough
   `support` signs to reach its question target (8 / 9 / 10 by severity).
3. Run `python scripts/validate_kb.py`. It reports unknown ids or answers, two
   rules that could fire on the same answers, rules with fewer than 8 signs, and rules that cannot be fully confirmed.
4. Run `pytest -q`. Every rule is tested automatically.

## Photo credits
Plant photos are from Wikimedia Commons under free licences. Authors and licences are in
`assets/plants/credits.json` and in the app sidebar ("Photo credits").

## Limitations
* The knowledge comes from general extension-service guidance (see `sources.json`),
  not lab tests. It covers common problems only.
* "Confirmed" means confirmed against the rules in this knowledge base, not a lab
  diagnosis. That is why every prescription suggests an expert check before chemicals.
