"""
Plant Care Expert - Streamlit interface.

    streamlit run streamlit_app.py

Flow: choose plant -> choose symptom -> answer questions
      -> the problem and its prescription.
"""
import json
from pathlib import Path

import streamlit as st

from engine.inference_engine import (
    EXPERT_NOTE_UNCONFIRMED,
    MIN_QUESTIONS,
    NONE_OF_THESE,
    NOT_SURE,
    answer_label,
    build_tree,
    conditions_checked,
    format_report,
    get_plant,
    get_plants,
    get_question,
    get_symptom,
    get_symptoms,
    next_step,
    path_to_dot,
    tree_to_dot,
)

st.set_page_config(page_title="Plant Care Expert", page_icon="🌿", layout="wide")

ASSETS = Path(__file__).resolve().parent / "assets" / "plants"
STEPS = [("plant", "Plant"), ("symptom", "Problem"), ("questions", "Questions"), ("result", "Prescription")]
SEVERITY = {"low": ("Mild", "green"), "medium": ("Moderate", "orange"), "high": ("Serious", "red")}

# Draws the decision tree at its real size inside a scrollable box (Graphviz via viz.js).
TREE_VIEWER = """
<div style="font-family:sans-serif;font-size:14px;margin-bottom:6px;color:#5d6b62;">
  <button id="zo" style="padding:4px 12px;border-radius:8px;border:1px solid #c5d1c9;background:#fff;cursor:pointer;">&minus;</button>
  <button id="zi" style="padding:4px 12px;border-radius:8px;border:1px solid #c5d1c9;background:#fff;cursor:pointer;">+</button>
  <button id="zf" style="padding:4px 12px;border-radius:8px;border:1px solid #c5d1c9;background:#fff;cursor:pointer;">Fit to width</button>
  <span style="margin-left:8px;">Zoom, then scroll inside the box</span>
</div>
<div id="box" style="overflow:auto;height:500px;border:1px solid #dce5de;border-radius:12px;background:#ffffff;
     font-family:sans-serif;color:#5d6b62;padding:6px;">Drawing the tree...</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/viz.js/2.1.2/viz.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/viz.js/2.1.2/full.render.js"></script>
<script>
  const box = document.getElementById('box');
  let svg = null, W = 0, H = 0, scale = 0.7;
  function apply() {
    svg.setAttribute('width', (W * scale) + 'pt');
    svg.setAttribute('height', (H * scale) + 'pt');
  }
  function fail() { box.textContent = 'Could not draw the tree here. Use the compact view below.'; }
  try {
    new Viz().renderSVGElement(__DOT__).then(function (el) {
      svg = el; W = parseFloat(svg.getAttribute('width')); H = parseFloat(svg.getAttribute('height'));
      box.innerHTML = ''; box.appendChild(svg); apply();
      box.scrollTop = (box.scrollHeight - box.clientHeight) / 2;
    }).catch(fail);
  } catch (e) { fail(); }
  document.getElementById('zi').onclick = function () { if (svg) { scale *= 1.25; apply(); } };
  document.getElementById('zo').onclick = function () { if (svg) { scale /= 1.25; apply(); } };
  document.getElementById('zf').onclick = function () {
    if (svg) { scale = (box.clientWidth - 24) / (W * 1.3333); apply(); }
  };
</script>
"""

CSS = """
<style>
.block-container { max-width: 1080px; padding-top: 4.2rem; padding-bottom: 4rem; }
.hero { background: linear-gradient(120deg, #14573a 0%, #1f7a4a 55%, #3fa56b 100%);
        border-radius: 20px; padding: 26px 32px; color: #ffffff; margin-bottom: 14px; }
.hero .title { font-size: 2.1rem; font-weight: 800; line-height: 1.2; color: #ffffff; }
.hero .tag { margin-top: 6px; font-size: 1.02rem; color: #e6f4ea; }
.stepper { display: flex; gap: 8px; margin: 6px 0 20px 0; }
.stepper .step { flex: 1; display: flex; align-items: center; gap: 10px; padding: 9px 12px;
                 border-radius: 12px; background: #eaf0ec; color: #5d6b62; font-weight: 600; font-size: .92rem; }
.stepper .n { width: 26px; height: 26px; border-radius: 50%; background: #c5d1c9; color: #ffffff;
              display: flex; align-items: center; justify-content: center; font-size: .85rem; flex-shrink: 0; }
.stepper .done { color: #14573a; background: #e6f4ea; }
.stepper .done .n { background: #3fa56b; }
.stepper .active { color: #14573a; background: #ffffff; box-shadow: inset 0 0 0 2px #1f7a4a; }
.stepper .active .n { background: #1f7a4a; }
@media (max-width: 700px) { .stepper .t { display: none; } .hero .title { font-size: 1.5rem; } }
div[data-testid="stImage"] img { border-radius: 14px; }
.stButton > button { border-radius: 12px; font-weight: 600; }
.qtext { font-size: 1.45rem; font-weight: 700; line-height: 1.35; color: #1b2a21; margin: 2px 0 2px 0; }
.qur { color: #5d6b62; margin-bottom: 10px; }
.icon-big { font-size: 1.9rem; line-height: 1; }
</style>
"""


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------
def init_state():
    defaults = {"step": "plant", "plant_id": None, "symptom_id": None, "answers": {}}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def start_over():
    st.session_state.step = "plant"
    st.session_state.plant_id = None
    st.session_state.symptom_id = None
    st.session_state.answers = {}


def choose_plant(plant_id):
    st.session_state.plant_id = plant_id
    st.session_state.step = "symptom"


def choose_symptom(symptom_id):
    st.session_state.symptom_id = symptom_id
    st.session_state.answers = {}
    st.session_state.step = "questions"


def answer(question_id, value):
    st.session_state.answers[question_id] = value


def go_back():
    answers = st.session_state.answers
    if answers:
        answers.pop(list(answers)[-1])
        st.session_state.step = "questions"
    elif st.session_state.step == "questions":
        st.session_state.step = "symptom"
    elif st.session_state.step == "symptom":
        st.session_state.step = "plant"


def other_symptom():
    st.session_state.answers = {}
    st.session_state.symptom_id = None
    st.session_state.step = "symptom"


# ---------------------------------------------------------------------------
# Shared UI pieces
# ---------------------------------------------------------------------------
def plant_photo(plant_id):
    path = ASSETS / f"{plant_id}.jpg"
    return str(path) if path.exists() else None


def show_photo(plant_id):
    photo = plant_photo(plant_id)
    if photo:
        st.image(photo, width="stretch")


def show_header():
    st.markdown(
        '<div class="hero"><div class="title">🌿 Plant Care Expert</div>'
        '<div class="tag">Answer a few simple questions to find out what is wrong with your '
        'houseplant and exactly what to do about it.</div></div>',
        unsafe_allow_html=True,
    )
    current = [key for key, _ in STEPS].index(st.session_state.step)
    items = []
    for i, (_, label) in enumerate(STEPS):
        state = "done" if i < current else "active" if i == current else ""
        mark = "✓" if i < current else str(i + 1)
        items.append(f'<div class="step {state}"><div class="n">{mark}</div><span class="t">{label}</span></div>')
    st.markdown('<div class="stepper">' + "".join(items) + "</div>", unsafe_allow_html=True)


def show_sidebar():
    with st.sidebar:
        st.subheader("How it works")
        st.markdown(
            "1. Pick your plant and the main problem.\n"
            "2. Answer the questions. Each answer rules out problems that don't fit.\n"
            "3. When the problem is confirmed, you get a prescription: what to do, "
            "what to avoid and how to prevent it."
        )
        st.info("This program gives guidance, not a guarantee. For serious problems, "
                "show your plant to a nursery or plant expert.", icon="🧑‍🌾")
        st.button("↺ Start over", on_click=start_over, width="stretch")
        credits_file = ASSETS / "credits.json"
        if credits_file.exists():
            with st.expander("📷 Photo credits"):
                credits = json.loads(credits_file.read_text(encoding="utf-8"))
                for plant_id, info in credits.items():
                    name = get_plant(plant_id)["common_name"]
                    st.markdown(f"**{name}**: [{info['photo']}]({info['source']}) by {info['author']}, "
                                f"{info['license']} (Wikimedia Commons)")


def show_plant_banner():
    """Photo + plant name + key care facts, shown on the next screens."""
    plant = get_plant(st.session_state.plant_id)
    col_photo, col_info = st.columns([1, 3], vertical_alignment="center")
    with col_photo:
        show_photo(plant["plant_id"])
    with col_info:
        parts = [f"### {plant['common_name']}"]
        if st.session_state.symptom_id:
            parts.append(f"**Problem:** {get_symptom(st.session_state.symptom_id)['name']}")
        st.markdown("\n\n".join(parts))
        st.caption(f"*{plant['scientific_name']}*")
    return plant


def show_answers(answers):
    for qid, value in answers.items():
        st.markdown(f"- {get_question(qid)['text']} → **{answer_label(qid, value)}**")


def numbered(items):
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))


def bullets(items):
    return "\n".join(f"- {item}" for item in items)


STATE_TEXT = {
    "confirmed": "✅ Confirmed",
    "closest": "🟡 Closest match",
    "possible": "❓ Still possible",
    "ruled_out": "❌ Ruled out",
    "other_symptom": "➖ Not relevant",
}


def show_how_we_checked(answers, outcome=None):
    """Your path, the full decision tree, and the status of every condition."""
    plant_id, symptom_id = st.session_state.plant_id, st.session_state.symptom_id
    rows = conditions_checked(plant_id, symptom_id, answers)
    relevant = [r for r in rows if r["state"] != "other_symptom"]
    ruled_out = sum(1 for r in rows if r["state"] == "ruled_out")
    other = len(rows) - len(relevant)

    tab_tree, tab_path, tab_checked = st.tabs(
        ["🌳 Decision tree", "🧭 Your path", f"📋 All {len(rows)} conditions checked"])
    with tab_tree:
        st.caption("The decision tree for this plant and problem. Each box is a question that splits the "
                   "possibilities, and each end box is a problem. After reaching a problem, a few "
                   "confirming questions follow (shown as +N). Your path is green; branches that do not "
                   "match your answers are pruned (grey). Use the zoom buttons and scroll inside the box.")
        dot = tree_to_dot(build_tree(plant_id, symptom_id), answers)
        st.iframe(TREE_VIEWER.replace("__DOT__", json.dumps(dot)).strip(), height=580)
        with st.expander("Compact view (fits the page, smaller text)"):
            st.graphviz_chart(dot)
    with tab_path:
        st.caption("Your questions and answers in order. After each answer, the conditions that no longer "
                   "fit are pruned, so the list shrinks until one problem is left.")
        if answers:
            st.graphviz_chart(path_to_dot(plant_id, symptom_id, answers, outcome))
        else:
            st.caption("No answers yet.")
    with tab_checked:
        st.caption(f"{len(rows)} conditions exist for this plant. {other} belong to other symptoms, so "
                   f"{len(relevant)} were checked against your answers and {ruled_out} were ruled out.")
        table = [{"Condition": r["problem"], "Rule": r["rule_id"], "Status": STATE_TEXT[r["state"]],
                  "Why": r["why"]} for r in rows]
        st.dataframe(table, hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------
def screen_plant():
    st.subheader("Which plant needs a check-up?")
    st.caption("Kis podey ka muayana karna hai?")
    columns = st.columns(3)
    for i, plant in enumerate(get_plants()):
        with columns[i % 3].container(border=True):
            show_photo(plant["plant_id"])
            st.markdown(f"#### {plant['common_name']}")
            st.caption(f"*{plant['scientific_name']}*")
            st.button("Select this plant →", key=f"plant_{plant['plant_id']}", on_click=choose_plant,
                      args=(plant["plant_id"],), width="stretch", type="primary")


def screen_symptom():
    plant = show_plant_banner()
    care = plant["care"]
    with st.container(border=True):
        st.markdown(f"**💧 Water:** {care['water']}  \n**☀️ Light:** {care['light']}")
    st.subheader("What is the main problem you see?")
    st.caption("Sab se numayan masla kya hai?")
    columns = st.columns(3)
    for i, symptom in enumerate(get_symptoms(st.session_state.plant_id)):
        with columns[i % 3].container(border=True):
            st.markdown(f"<div class='icon-big'>{symptom['icon']}</div>", unsafe_allow_html=True)
            st.markdown(f"**{symptom['name']}**")
            st.caption(f"{symptom['name_ur']} · {symptom['description']}")
            st.button("Choose", key=f"sym_{symptom['id']}", on_click=choose_symptom,
                      args=(symptom["id"],), width="stretch")
    st.button("← Back to plants", on_click=go_back)


def screen_questions():
    show_plant_banner()
    answers = st.session_state.answers
    step = next_step(st.session_state.plant_id, st.session_state.symptom_id, answers)
    if step["status"] != "ask":
        st.session_state.step = "result"
        st.rerun()

    question = step["question"]
    count = len(answers) + 1
    st.progress(min(len(answers) / MIN_QUESTIONS, 1.0),
                text=f"Question {count} · we ask at least {MIN_QUESTIONS} questions so the answer is reliable")
    with st.container(border=True):
        st.markdown(f"<div class='qtext'>{question['text']}</div>"
                    f"<div class='qur'>{question['text_ur']}</div>", unsafe_allow_html=True)
        values = [o["value"] for o in question["options"]]
        if values == ["yes", "no"]:
            col_yes, col_no = st.columns(2)
            col_yes.button("✅ Yes", key=f"opt_{question['id']}_yes_{len(answers)}", on_click=answer,
                           args=(question["id"], "yes"), width="stretch")
            col_no.button("❌ No", key=f"opt_{question['id']}_no_{len(answers)}", on_click=answer,
                          args=(question["id"], "no"), width="stretch")
        else:
            for option in question["options"]:
                st.button(option["label"], key=f"opt_{question['id']}_{option['value']}_{len(answers)}",
                          on_click=answer, args=(question["id"], option["value"]), width="stretch")
        col_unsure, col_none = st.columns(2)
        col_unsure.button("🤷 Not sure", key=f"unsure_{len(answers)}", on_click=answer,
                          args=(question["id"], NOT_SURE), width="stretch")
        col_none.button("None of these", key=f"none_{len(answers)}", on_click=answer,
                        args=(question["id"], NONE_OF_THESE), width="stretch")

    st.button("← Back", on_click=go_back)
    if answers:
        with st.expander(f"Your answers so far ({len(answers)})"):
            show_answers(answers)
    with st.expander("🌳 How the conditions are being checked"):
        show_how_we_checked(answers)


def show_problem_card(name, about, category=None, severity=None, note=""):
    plant = get_plant(st.session_state.plant_id)
    col_photo, col_info = st.columns([1, 2], vertical_alignment="center")
    with col_photo:
        show_photo(plant["plant_id"])
    with col_info:
        st.caption(f"Your {plant['common_name']}'s problem")
        st.markdown(f"## {name}")
        if category:
            badge_cols = st.columns([1, 1, 3])
            badge_cols[0].badge(category, color="blue")
            label, colour = SEVERITY[severity]
            badge_cols[1].badge(label, color=colour)
        st.write(about)
        if note:
            st.info(note, icon="🪴")


def show_steps(steps):
    st.markdown("#### 💊 What to do")
    for i, text in enumerate(steps, 1):
        with st.container(border=True):
            st.markdown(f"**Step {i}**  \n{text}")


def show_avoid_prevent(avoid, prevent):
    col_avoid, col_prevent = st.columns(2)
    with col_avoid.container(border=True):
        st.markdown("**🚫 Avoid**")
        st.markdown(bullets(avoid))
    with col_prevent.container(border=True):
        st.markdown("**🛡️ Prevent it next time**")
        st.markdown(bullets(prevent))


def show_prescription(result):
    cond = result["condition"]
    show_problem_card(cond["name"], cond["about"], cond["category"], cond["severity"], result["note"])
    if result["closest"]:
        st.warning("**Closest match.** The main signs of this problem fit your plant, but some "
                   "supporting signs did not. Treat the advice below as a careful first step.", icon="🟡")
    show_steps(cond["steps"])
    show_avoid_prevent(cond["avoid"], cond["prevent"])
    st.caption(f"🧑‍🌾 {result['expert_note']}")


def screen_result():
    plant = get_plant(st.session_state.plant_id)
    answers = st.session_state.answers
    step = next_step(st.session_state.plant_id, st.session_state.symptom_id, answers)

    if step["status"] == "diagnosed":
        show_prescription(step["diagnosis"])

    elif step["status"] == "possibilities":
        show_plant_banner()
        st.warning("Some answers were 'Not sure', so the problem is one of these. "
                   "Check those signs again for a clear answer.", icon="🤔")
        for result in step["results"][:4]:
            cond = result["condition"]
            with st.expander(cond["name"]):
                st.write(cond["about"])
                st.markdown("**What to do:**\n" + numbered(cond["steps"]))
                st.markdown("**Avoid:**\n" + bullets(cond["avoid"]))
        st.caption(f"🧑‍🌾 {EXPERT_NOTE_UNCONFIRMED}")

    else:  # no_match: general care terminal node
        general = step["general"]
        show_problem_card(general["name"], general["about"])
        show_steps(general["steps"])
        show_avoid_prevent(general["avoid"], general["prevent"])
        st.caption("🧑‍🌾 Please show the plant to a nursery or plant expert. You can also go back "
                   "and change an answer you were unsure about.")

    with st.expander(f"🪴 General care for {plant['common_name']}"):
        for key, value in plant["care"].items():
            st.markdown(f"- **{key.title()}:** {value}")

    if step["status"] == "diagnosed":
        outcome = step["diagnosis"]["condition"]["name"]
    elif step["status"] == "no_match":
        outcome = step["general"]["name"]
    else:
        outcome = "Several possible problems"
    st.markdown("#### 🌳 How we reached this answer")
    show_how_we_checked(answers, outcome)

    st.download_button(
        "⬇️ Download prescription",
        data=format_report(st.session_state.plant_id, st.session_state.symptom_id, answers, step),
        file_name=f"prescription_{st.session_state.plant_id}.txt",
        mime="text/plain",
        width="stretch",
    )
    col_back, col_other, col_new = st.columns(3)
    col_back.button("← Change last answer", on_click=go_back, width="stretch")
    col_other.button("Check another problem", on_click=other_symptom, width="stretch")
    col_new.button("Start over", on_click=start_over, width="stretch", type="primary")


# ---------------------------------------------------------------------------
init_state()
st.markdown(CSS, unsafe_allow_html=True)
show_sidebar()
show_header()
{
    "plant": screen_plant,
    "symptom": screen_symptom,
    "questions": screen_questions,
    "result": screen_result,
}[st.session_state.step]()
