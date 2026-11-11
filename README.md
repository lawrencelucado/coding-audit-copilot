# Coding Audit Copilot

An AI assistant that proposes professional-fee medical codes (ICD-10-CM, CPT/HCPCS) for an outpatient note, **checks every code against official CMS rules with deterministic tools**, and is **scored against answers from a certified coder (CPC)**.

> **The model reasons, the tools decide anything that must be exact.**
> Code validity, NCCI bundling edits and unit limits come from CMS files, never from the model's memory. Every code carries evidence from the note, and a certified coder makes the final call.

**Status:** v0.1. First evaluation: diagnosis F1 0.974 and 100% first-listed accuracy on 11 CPC-reviewed cases, at $0.036 per chart (see [Results](#results)).

## Architecture

```
clinical note ──► Claude agent (Opus 5.5, adaptive thinking, effort=high)
                     │  reasons about diagnoses, procedures, guidelines
                     ▼
               deterministic tools ─────────────────────────────┐
                 icd10_lookup / icd10_search  ◄─ CMS ICD-10-CM FY file (public domain)
                 ncci_ptp_check               ◄─ CMS NCCI PTP edits (licensed, local only)
                 mue_check                    ◄─ CMS MUE file (licensed, local only)
                     │
                     ▼
               submit_coding (Pydantic-validated JSON, evidence per code)
                     │
                     ▼
         certified coder review ──► disagreements become new eval cases
```

Every run records a trace: turns, tool calls, input/output/cache tokens, cost in USD, latency, fallback use and errors (`results/<run>/traces.jsonl`).

## Evaluation

`evals/cases/` holds synthetic encounters (fictional patients) with answer keys written by a certified coder. The scorer reports:

| Metric | What it measures |
|---|---|
| Diagnosis precision / recall / F1 | Right ICD-10-CM codes, no extras (accepted alternates and optional codes such as external-cause codes are configurable per case) |
| First-listed accuracy | Correct sequencing of the first-listed diagnosis |
| Procedure precision / recall | Right CPT/HCPCS codes |
| Modifier accuracy | e.g. modifier 25 on a separately identifiable E/M |
| Edit-flag recall | Did the agent flag each NCCI/MUE issue the expert expects |
| Exact-match rate | Whole encounter correct |
| Cost / latency per case | From the traces |

Cases test real guideline traps: combination codes (hypertension with heart failure → I11.0; with CKD → I12.9), "probable" diagnoses in outpatient care (code the symptoms), modifier 25 with a joint injection, pathogen secondary codes, and COVID-19 sequencing.

**CI gate:** `python -m evals.run --min-dx-f1 0.85` exits non-zero below the bar, so a prompt or model change that lowers accuracy fails the pull request (`.github/workflows/ci.yml`).

## Results

| Run | Model / effort | Cases | Dx F1 | First-listed | Px F1 | Exact match | Cost per case |
|---|---|---|---|---|---|---|---|
| 2026-11-11 | claude-opus-5-5 / high | 11 | 0.974 | 100% | 1.00 | 82% (9/11) | $0.036 (avg 14.9 s) |
| 2026-11-11, re-scored | same predictions, revised keys | 11 | 1.00 | 100% | 1.00 | 100% (11/11) | no new API calls |

The two original misses were optional details, not wrong core codes: case_003 added a place-of-occurrence code (Y92.009, since the note says only "at home"), and case_004 added an informational RT modifier to 20610. On review, the CPC accepted both, and the answer keys now list them as acceptable. `python -m evals.rescore` re-grades a saved run against revised keys without calling the model.

**Limits:** 11 synthetic cases is a small set, and the CPC who reviewed the keys also built the project. NCCI/MUE files were not loaded, so edit-flag detection is untested. Next: 50+ cases and a run with bundling edits loaded.

## Data setup

1. **ICD-10-CM (public domain):** download "Code Descriptions in Tabular Order" for your fiscal year from [CMS ICD-10](https://www.cms.gov/medicare/coding-billing/icd-10-codes), or run `python scripts/fetch_icd10.py <zip-url>`. The loader looks for `data/**/icd10cm_order_<FY>.txt`.
2. **NCCI PTP and MUE (optional, licensed):** these files contain AMA CPT content. Accept the CMS license yourself, download the **practitioner** files, and unzip them to `data/ptp/` and `data/mue/`. They are git-ignored and must never be committed or redistributed. Without them the tools answer "unavailable" and the agent says so.

## Run it

```bash
python -m venv .venv && .venv/Scripts/activate      # Windows; use bin/activate elsewhere
pip install -e ".[dev]"
pytest -q                                            # 17 offline tests, no API key needed
python scripts/make_cases.py                         # regenerate the starter cases
export ANTHROPIC_API_KEY=...                         # your own key
python -m evals.run                                  # agent + scoring + report
```

Settings via environment variables: `CAC_MODEL`, `CAC_EFFORT`, `CAC_MAX_TURNS`, `CAC_ICD10_FY`, `CAC_DATA_DIR`.

## Safety and compliance

- Synthetic notes only. No PHI is stored, logged or committed.
- Outputs are proposals for a certified coder, not claims.
- Licensed CMS/AMA data stays local; the repository contains only code and synthetic cases.
- Fiscal-year awareness: ICD-10-CM changes every October 1, so codes are validated against the file for the encounter's year. Version mismatches are a form of data drift the evaluation catches.

## Roadmap

- [ ] Coder-reviewed answer keys for all cases, then grow to 100+ cases
- [ ] Retrieval (pgvector) over public coding guidance with citations
- [ ] PHI redaction step (Presidio) in front of the model
- [ ] FastAPI service, Docker image, Langfuse tracing and Grafana cost/quality dashboards
- [ ] Effort and model sweep: accuracy vs. cost per case
