"""Paths and runtime settings, all overridable by environment variables."""
from __future__ import annotations

import os
from glob import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("CAC_DATA_DIR", ROOT / "data"))

MODEL = os.environ.get("CAC_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("CAC_EFFORT", "high")
MAX_TURNS = int(os.environ.get("CAC_MAX_TURNS", "12"))

# Fiscal year of the ICD-10-CM order file you downloaded (FY runs Oct 1 - Sep 30).
ICD10_FY = int(os.environ.get("CAC_ICD10_FY", "2026"))


def icd10_order_file() -> Path | None:
    hits = sorted(glob(str(DATA_DIR / "**" / f"icd10cm_order_{ICD10_FY}.txt"), recursive=True))
    return Path(hits[0]) if hits else None


def ptp_files() -> list[Path]:
    # Practitioner PTP edits only (pro-fee). Hospital files are "ccioph".
    return [Path(p) for p in sorted(glob(str(DATA_DIR / "ptp" / "**" / "*.txt"), recursive=True))
            if "ccipra" in p.lower() or "practitioner" in p.lower()]


def mue_file() -> Path | None:
    hits = sorted(glob(str(DATA_DIR / "mue" / "**" / "*ractitioner*.csv"), recursive=True))
    return Path(hits[0]) if hits else None
