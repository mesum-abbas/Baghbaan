
import engine.inference_engine as inference


def test_unapproved_rules_are_ignored(monkeypatch):
    monkeypatch.setattr(
        inference,
        "load_rules",
        lambda: [
            {
                "rule_id": "TEST001",
                "plant_id": "money_plant",
                "symptom": "yellow_leaves",
                "possible_cause": "overwatering",
                "indicators": ["soil_stays_wet"],
                "recommended_action": "Check soil moisture.",
                "approved": False,
                "evidence_reviewed": False
            }
        ]
    )

    result = inference.diagnose(
        "money_plant",
        "yellow_leaves",
        {"soil_stays_wet": True}
    )

    assert result == []


def test_approved_matching_rule_is_returned(monkeypatch):
    monkeypatch.setattr(
        inference,
        "load_rules",
        lambda: [
            {
                "rule_id": "TEST002",
                "plant_id": "money_plant",
                "symptom": "yellow_leaves",
                "possible_cause": "overwatering",
                "indicators": ["soil_stays_wet"],
                "recommended_action": "Check soil moisture.",
                "approved": True,
                "evidence_reviewed": True,
                "confidence": "low",
                "source_ids": ["PLSRC001"]
            }
        ]
    )

    result = inference.diagnose(
        "money_plant",
        "yellow_leaves",
        {"soil_stays_wet": True}
    )

    assert len(result) == 1
    assert result[0]["rule_id"] == "TEST002"
    assert result[0]["evidence_score_percent"] == 100


def test_wrong_plant_or_symptom_returns_no_rule(monkeypatch):
    monkeypatch.setattr(
        inference,
        "load_rules",
        lambda: [
            {
                "rule_id": "TEST003",
                "plant_id": "money_plant",
                "symptom": "yellow_leaves",
                "possible_cause": "overwatering",
                "indicators": ["soil_stays_wet"],
                "recommended_action": "Check soil moisture.",
                "approved": True,
                "evidence_reviewed": True,
                "confidence": "low",
                "source_ids": ["PLSRC001"]
            }
        ]
    )

    assert inference.diagnose(
        "snake_plant",
        "yellow_leaves",
        {"soil_stays_wet": True}
    ) == []

    assert inference.diagnose(
        "money_plant",
        "brown_tips_edges",
        {"soil_stays_wet": True}
    ) == []


def test_missing_answers_do_not_create_a_score(monkeypatch):
    monkeypatch.setattr(
        inference,
        "load_rules",
        lambda: [
            {
                "rule_id": "TEST004",
                "plant_id": "money_plant",
                "symptom": "yellow_leaves",
                "possible_cause": "overwatering",
                "indicators": ["soil_stays_wet"],
                "recommended_action": "Check soil moisture.",
                "approved": True,
                "evidence_reviewed": True,
                "confidence": "low",
                "source_ids": ["PLSRC001"]
            }
        ]
    )

    result = inference.diagnose(
        "money_plant",
        "yellow_leaves",
        {}
    )

    assert len(result) == 1
    assert result[0]["evidence_score_percent"] is None
    assert result[0]["indicators_to_check"] == ["soil_stays_wet"]
