"""Run the agent over every case and write a scored report.

    python -m evals.run                      # all cases
    python -m evals.run --cases case_001 case_004
    python -m evals.run --min-dx-f1 0.85     # CI gate: exit 1 below the bar

Writes results/<timestamp>/ with predictions.jsonl, traces.jsonl and report.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic

from copilot import config
from copilot.agent import CodingAgent, load_tables
from evals.score import aggregate, score_case

CASES_DIR = Path(__file__).parent / "cases"


def load_cases(ids: list[str] | None) -> list[dict]:
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CASES_DIR.glob("*.json"))]
    return [c for c in cases if not ids or c["id"] in ids]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="*")
    ap.add_argument("--min-dx-f1", type=float, default=None)
    args = ap.parse_args()

    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("No API key found. Set it in this terminal first, e.g. in PowerShell:\n"
              '  $env:ANTHROPIC_API_KEY = "<your key>"')
        return 2

    cases = load_cases(args.cases)
    icd10, ncci = load_tables()
    agent = CodingAgent(icd10, ncci)
    out = config.ROOT / "results" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)

    scores, traces = [], []
    with open(out / "predictions.jsonl", "w", encoding="utf-8") as pf, \
         open(out / "traces.jsonl", "w", encoding="utf-8") as tf:
        for case in cases:
            try:
                result, trace = agent.code_encounter(case["id"], case["note"], case["date_of_service"])
            except anthropic.AuthenticationError:
                print("API key rejected. Set a valid key: $env:ANTHROPIC_API_KEY = \"<your key>\"")
                return 3
            except anthropic.BadRequestError as exc:
                if "credit balance" in str(exc).lower():
                    print("No API credits on this account. Add funds in the Claude Console "
                          "(Settings > Billing), then run again.")
                    return 3
                raise
            except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
                print(f"{case['id']}: API error, skipped ({type(exc).__name__}: {exc})")
                continue
            pred = result.model_dump() if result else None
            s = score_case(case, pred)
            scores.append(s)
            traces.append(trace)
            pf.write(json.dumps({"id": case["id"], "prediction": pred}) + "\n")
            tf.write(json.dumps(trace.as_dict()) + "\n")
            status = "EXACT" if s.exact else f"miss dx {s.missed_dx} extra {s.extra_dx} miss px {s.missed_px}"
            print(f"{case['id']}: {status}  ({trace.turns} turns, ${trace.cost_usd:.4f}, {trace.latency_s}s)")

    summary = aggregate(scores)
    summary.update({
        "model": config.MODEL, "effort": config.EFFORT, "icd10_fy": config.ICD10_FY,
        "ncci_loaded": ncci.loaded,
        "total_cost_usd": round(sum(t.cost_usd for t in traces), 4),
        "avg_cost_per_case_usd": round(sum(t.cost_usd for t in traces) / max(len(traces), 1), 4),
        "avg_latency_s": round(sum(t.latency_s for t in traces) / max(len(traces), 1), 2),
        "errors": [f"{t.case_id}: {t.error}" for t in traces if t.error],
    })
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    lines = ["# Evaluation report", "", "| Metric | Value |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in summary.items()]
    lines += ["", "## Per case", "", "| Case | Exact | Missed dx | Extra dx | Missed px | Extra px | Flags |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {s.case_id} | {'yes' if s.exact else 'no'} | {', '.join(s.missed_dx)} | {', '.join(s.extra_dx)} | "
              f"{', '.join(s.missed_px)} | {', '.join(s.extra_px)} | {s.flags_found}/{s.flags_expected} |" for s in scores]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Report: {out / 'report.md'}")

    if args.min_dx_f1 is not None and summary["dx_f1"] < args.min_dx_f1:
        print(f"FAIL: dx_f1 {summary['dx_f1']} < {args.min_dx_f1}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
