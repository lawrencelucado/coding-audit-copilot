"""ICD-10-CM code table loaded from the CMS/CDC "order" file.

ICD-10-CM is published by CDC/CMS and is in the public domain. Download the
fiscal-year "code descriptions in tabular order" file from
https://www.cms.gov/medicare/coding-billing/icd-10-codes and point this loader
at ``icd10cm_order_<year>.txt``.

Order-file layout (fixed width):
    cols 1-5   order number
    col  7-13  code, no dot, left-justified
    col  15    1 = billable (valid for HIPAA transactions), 0 = header
    col  17-76 short description
    col  78-   long description
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Icd10Code:
    code: str          # dotted form, e.g. "E11.65"
    billable: bool
    short_desc: str
    long_desc: str


def normalize(code: str) -> str:
    """Return the undotted, upper-case form used in CMS files."""
    return code.replace(".", "").strip().upper()


def dotted(code: str) -> str:
    c = normalize(code)
    return c if len(c) <= 3 else f"{c[:3]}.{c[3:]}"


class Icd10Table:
    def __init__(self, codes: dict[str, Icd10Code], fiscal_year: int):
        self._codes = codes
        self.fiscal_year = fiscal_year

    @classmethod
    def from_order_file(cls, path: str | Path, fiscal_year: int) -> "Icd10Table":
        codes: dict[str, Icd10Code] = {}
        with open(path, encoding="latin-1") as fh:
            for line in fh:
                if len(line) < 17:
                    continue
                raw = line[6:13].strip()
                if not raw:
                    continue
                codes[raw] = Icd10Code(
                    code=dotted(raw),
                    billable=line[14] == "1",
                    short_desc=line[16:76].strip(),
                    long_desc=line[77:].strip(),
                )
        if not codes:
            raise ValueError(f"No ICD-10-CM codes parsed from {path}")
        return cls(codes, fiscal_year)

    def __len__(self) -> int:
        return len(self._codes)

    def lookup(self, code: str) -> dict:
        """Validate one code. Never guesses: unknown codes are reported as not found."""
        key = normalize(code)
        entry = self._codes.get(key)
        if entry is None:
            return {"code": dotted(key), "fiscal_year": self.fiscal_year, "found": False,
                    "billable": False, "message": "Code does not exist in this fiscal year's ICD-10-CM file."}
        result = {"code": entry.code, "fiscal_year": self.fiscal_year, "found": True,
                  "billable": entry.billable, "description": entry.long_desc}
        if not entry.billable:
            children = [c.code for k, c in self._codes.items() if k.startswith(key) and k != key and c.billable]
            result["message"] = "Header code: not valid for billing. Code to a more specific child."
            result["billable_children_sample"] = children[:15]
        return result

    def search(self, query: str, limit: int = 15) -> list[dict]:
        """Keyword search over long descriptions (all terms must match). Billable codes first."""
        terms = [t.lower() for t in query.split() if t.strip()]
        if not terms:
            return []
        hits = [c for c in self._codes.values() if all(t in c.long_desc.lower() for t in terms)]
        hits.sort(key=lambda c: (not c.billable, len(c.code), c.code))
        return [{"code": c.code, "billable": c.billable, "description": c.long_desc} for c in hits[:limit]]
