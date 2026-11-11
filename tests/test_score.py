from evals.score import aggregate, score_case

CASE = {
    "id": "t1",
    "gold": {
        "diagnoses": [{"code": "E11.65"}, {"code": "I10"}],
        "first_listed": "E11.65",
        "optional_dx": ["Z79.84"],
        "procedures": [{"code": "20610"}, {"code": "99213", "modifiers": ["25"]}],
        "edit_flags_expected": [{"codes": ["20610", "99213"]}],
    },
}


def pred(dx, px, flags=()):
    return {"diagnoses": [{"code": c, "sequence": i + 1, "evidence": ""} for i, c in enumerate(dx)],
            "procedures": [{"code": c, "modifiers": m, "units": 1, "evidence": ""} for c, m in px],
            "edit_flags": list(flags)}


def test_exact_match():
    s = score_case(CASE, pred(["E11.65", "I10", "Z79.84"], [("20610", []), ("99213", ["25"])],
                              ["NCCI: 20610 / 99213 bundled, modifier 25 required"]))
    assert s.exact and s.first_listed_ok and s.flags_found == 1 and s.dx_fp == 0


def test_missing_modifier_and_wrong_first_listed():
    s = score_case(CASE, pred(["I10", "E11.65"], [("20610", []), ("99213", [])]))
    assert not s.exact and not s.modifiers_ok and not s.first_listed_ok and s.flags_found == 0


def test_extra_and_missed_codes():
    s = score_case(CASE, pred(["E11.9"], [("20610", [])]))
    assert s.missed_dx == ["E11.65", "I10"] and s.extra_dx == ["E119"] and s.missed_px == ["99213"]


def test_optional_modifier_is_not_penalized():
    case = {"id": "t2", "gold": {"diagnoses": [{"code": "M17.11"}], "first_listed": "M17.11",
                                 "procedures": [{"code": "20610", "optional_modifiers": ["RT"]}]}}
    assert score_case(case, pred(["M17.11"], [("20610", ["RT"])])).exact
    assert score_case(case, pred(["M17.11"], [("20610", [])])).exact
    assert not score_case(case, pred(["M17.11"], [("20610", ["LT"])])).exact


def test_no_prediction_scores_zero():
    agg = aggregate([score_case(CASE, None)])
    assert agg["dx_recall"] == 0 and agg["exact_match_rate"] == 0
