"""Medicare NCCI procedure-to-procedure (PTP) edits and Medically Unlikely Edits (MUEs).

LICENSING: the NCCI files contain CPT content licensed by the AMA. You must
accept the CMS "End User Point and Click Agreement" yourself and download the
files from:
  PTP: https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-procedure-procedure-ptp-edits
  MUE: https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-medically-unlikely-edits-mues
Keep them in ``data/`` (git-ignored). Never commit or redistribute them.

PTP practitioner .txt files are tab-delimited:
    Column 1 | Column 2 | * (in existence prior to 1996) | Effective date (YYYYMMDD)
    | Deletion date (YYYYMMDD or *) | Modifier indicator (0, 1, 9) | Rationale
MUE practitioner .csv:
    HCPCS/CPT code, MUE value, MUE adjudication indicator (MAI), rationale
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_CODE = re.compile(r"^[0-9A-Z]{5}$")

MODIFIER_MEANING = {
    "0": "Not allowed: the column 2 code is never separately payable with column 1, even with a modifier.",
    "1": "Allowed with an NCCI-associated modifier (e.g. 59, XE/XS/XP/XU, 25 for E/M) when documentation supports a distinct service.",
    "9": "Edit not applicable (deleted on its effective date).",
}

MAI_MEANING = {
    "1": "Line edit: units above the MUE on one claim line are denied.",
    "2": "Date-of-service edit, policy: absolute limit per day; not appealable on medical necessity.",
    "3": "Date-of-service edit, clinical: units above the MUE may be paid on appeal with documentation.",
}


def _parse_date(s: str) -> date | None:
    s = s.strip()
    if not s or s == "*":
        return None
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


@dataclass(frozen=True)
class PtpEdit:
    column1: str
    column2: str
    effective: date
    deleted: date | None
    modifier_indicator: str
    rationale: str

    def active_on(self, dos: date) -> bool:
        return self.effective <= dos and (self.deleted is None or dos < self.deleted)


class NcciTables:
    def __init__(self) -> None:
        self._ptp: dict[tuple[str, str], list[PtpEdit]] = {}
        self._mue: dict[str, tuple[int, str, str]] = {}

    # ---------- loading ----------
    def load_ptp_file(self, path: str | Path) -> int:
        n = 0
        with open(path, encoding="latin-1") as fh:
            for line in fh:
                parts = [p.strip() for p in line.rstrip("\n").split("\t")]
                if len(parts) < 6 or not _CODE.match(parts[0]) or not _CODE.match(parts[1]):
                    continue
                edit = PtpEdit(parts[0], parts[1], _parse_date(parts[3]), _parse_date(parts[4]),
                               parts[5], parts[6] if len(parts) > 6 else "")
                self._ptp.setdefault((edit.column1, edit.column2), []).append(edit)
                n += 1
        return n

    def load_mue_file(self, path: str | Path) -> int:
        n = 0
        with open(path, encoding="latin-1", newline="") as fh:
            for row in csv.reader(fh):
                if len(row) < 3 or not _CODE.match(row[0].strip()):
                    continue
                code, value, mai = row[0].strip(), row[1].strip(), row[2].strip()
                rationale = row[3].strip() if len(row) > 3 else ""
                try:
                    self._mue[code] = (int(value), mai[:1], rationale)
                except ValueError:
                    continue
                n += 1
        return n

    @property
    def loaded(self) -> bool:
        return bool(self._ptp or self._mue)

    # ---------- checks ----------
    def check_pair(self, code_a: str, code_b: str, dos: date) -> dict:
        a, b = code_a.strip().upper(), code_b.strip().upper()
        if not self._ptp:
            return {"status": "unavailable", "message": "PTP edit file not loaded."}
        for c1, c2 in ((a, b), (b, a)):
            for edit in self._ptp.get((c1, c2), []):
                if edit.active_on(dos):
                    return {"status": "edit", "column1": c1, "column2": c2,
                            "modifier_indicator": edit.modifier_indicator,
                            "meaning": MODIFIER_MEANING.get(edit.modifier_indicator, "Unknown indicator."),
                            "rationale": edit.rationale,
                            "effective": edit.effective.isoformat()}
        return {"status": "no_edit", "message": f"No active PTP edit between {a} and {b} on {dos.isoformat()}."}

    def check_units(self, code: str, units: int) -> dict:
        c = code.strip().upper()
        if not self._mue:
            return {"status": "unavailable", "message": "MUE file not loaded."}
        if c not in self._mue:
            return {"status": "no_mue", "message": f"No MUE published for {c}."}
        limit, mai, rationale = self._mue[c]
        return {"status": "exceeds" if units > limit else "ok", "code": c, "units": units,
                "mue": limit, "mai": mai, "mai_meaning": MAI_MEANING.get(mai, ""), "rationale": rationale}
