"""Score agent predictions against expert (CPC) answer keys.

Metrics
- Diagnosis precision / recall / F1 (a gold code may list accepted alternates)
- First-listed diagnosis accuracy
- Procedure precision / recall (code level) and modifier accuracy
- Edit-flag recall: did the agent flag each NCCI/MUE issue the expert expects
- Exact-match rate: every dx and procedure (with modifiers) correct
"""
from __future__ import annotations

from dataclasses import dataclass


def _norm(code: str) -> str:
    return code.replace(".", "").strip().upper()


@dataclass
class CaseScore:
    case_id: str
    dx_tp: int
    dx_fp: int
    dx_fn: int
    first_listed_ok: bool
    px_tp: int
    px_fp: int
    px_fn: int
    modifiers_ok: bool
    flags_expected: int
    flags_found: int
    exact: bool
    missed_dx: list[str]
    extra_dx: list[str]
    missed_px: list[str]
    extra_px: list[str]


def score_case(case: dict, pred: dict | None) -> CaseScore:
    gold = case["gold"]
    pred = pred or {"diagnoses": [], "procedures": [], "edit_flags": []}

    # Diagnoses: each gold entry is satisfied by its code or any listed alternate.
    pred_dx = [_norm(d["code"]) for d in sorted(pred["diagnoses"], key=lambda d: d.get("sequence", 99))]
    remaining = set(pred_dx)
    tp, missed = 0, []
    for g in gold["diagnoses"]:
        options = {_norm(g["code"]), *(_norm(a) for a in g.get("alternates", []))}
        match = options & remaining
        if match:
            tp += 1
            remaining -= {next(iter(match))}
        else:
            missed.append(g["code"])
    # Codes the expert considers acceptable but not required (e.g. external cause codes) are not penalized.
    remaining -= {_norm(c) for c in gold.get("optional_dx", [])}
    extra = sorted(remaining)
    first_gold = {_norm(gold["first_listed"]), *(_norm(a) for a in gold.get("first_listed_alternates", []))}
    first_ok = bool(pred_dx) and pred_dx[0] in first_gold

    # Procedures
    gold_px = {_norm(p["code"]): sorted(m.upper() for m in p.get("modifiers", [])) for p in gold["procedures"]}
    # Informational modifiers the expert accepts but does not require (e.g. RT/LT) are ignored when present.
    optional_mods = {_norm(p["code"]): {m.upper() for m in p.get("optional_modifiers", [])} for p in gold["procedures"]}
    pred_px = {_norm(p["code"]): sorted(m.upper() for m in p.get("modifiers", [])
                                        if m.upper() not in optional_mods.get(_norm(p["code"]), set()))
               for p in pred["procedures"]}
    px_tp = len(gold_px.keys() & pred_px.keys())
    modifiers_ok = all(pred_px.get(c) == m for c, m in gold_px.items() if c in pred_px)

    # Edit flags: a flag matches when it mentions every code in the expected pair.
    flags_text = " ".join(pred.get("edit_flags", [])).upper()
    expected = gold.get("edit_flags_expected", [])
    found = sum(1 for e in expected if all(_norm(c) in flags_text.replace(".", "") for c in e["codes"]))

    exact = (not missed and not extra and set(gold_px) == set(pred_px) and modifiers_ok)
    return CaseScore(case["id"], tp, len(extra), len(missed), first_ok,
                     px_tp, len(pred_px.keys() - gold_px.keys()), len(gold_px.keys() - pred_px.keys()),
                     modifiers_ok, len(expected), found, exact,
                     missed, extra, sorted(gold_px.keys() - pred_px.keys()), sorted(pred_px.keys() - gold_px.keys()))


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return round(p, 3), round(r, 3), round(f, 3)


def aggregate(scores: list[CaseScore]) -> dict:
    n = len(scores) or 1
    dx = _prf(sum(s.dx_tp for s in scores), sum(s.dx_fp for s in scores), sum(s.dx_fn for s in scores))
    px = _prf(sum(s.px_tp for s in scores), sum(s.px_fp for s in scores), sum(s.px_fn for s in scores))
    flags_exp = sum(s.flags_expected for s in scores)
    return {
        "cases": len(scores),
        "dx_precision": dx[0], "dx_recall": dx[1], "dx_f1": dx[2],
        "first_listed_accuracy": round(sum(s.first_listed_ok for s in scores) / n, 3),
        "px_precision": px[0], "px_recall": px[1], "px_f1": px[2],
        "modifier_accuracy": round(sum(s.modifiers_ok for s in scores) / n, 3),
        "edit_flag_recall": round(sum(s.flags_found for s in scores) / flags_exp, 3) if flags_exp else None,
        "exact_match_rate": round(sum(s.exact for s in scores) / n, 3),
    }
