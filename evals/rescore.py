"""Re-score a saved run against the current answer keys, with no API calls.

    python -m evals.rescore results/<run>

Use after an expert changes an answer key: the model output stays the same,
only the grading changes. Writes rescore.md next to the original report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from evals.run import load_cases
from evals.score import aggregate, score_case


def main() -> int:
    run = Path(sys.argv[1])
    preds = {json.loads(l)["id"]: json.loads(l)["prediction"]
             for l in (run / "predictions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    cases = [c for c in load_cases(None) if c["id"] in preds]
    scores = [score_case(c, preds[c["id"]]) for c in cases]
    summary = aggregate(scores)
    lines = [f"# Re-score of {run.name} against current answer keys", "", "| Metric | Value |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in summary.items()]
    lines += ["", "| Case | Exact |", "|---|---|"] + [f"| {s.case_id} | {'yes' if s.exact else 'no'} |" for s in scores]
    (run / "rescore.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
