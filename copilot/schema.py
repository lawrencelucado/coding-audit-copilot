"""The structured result the agent must submit, and the gold-answer format."""
from __future__ import annotations

from pydantic import BaseModel, Field


class DiagnosisCode(BaseModel):
    code: str = Field(description="ICD-10-CM code with dot, e.g. E11.65")
    evidence: str = Field(description="Exact phrase from the note that supports the code")
    sequence: int = Field(description="1 = first-listed diagnosis")


class ProcedureCode(BaseModel):
    code: str = Field(description="CPT/HCPCS code, e.g. 99214")
    modifiers: list[str] = Field(default_factory=list)
    units: int = 1
    evidence: str


class CodingResult(BaseModel):
    diagnoses: list[DiagnosisCode]
    procedures: list[ProcedureCode]
    edit_flags: list[str] = Field(
        default_factory=list,
        description="NCCI/MUE/validity issues found, e.g. 'NCCI: 20610/99213 needs modifier 25'")
    documentation_gaps: list[str] = Field(
        default_factory=list,
        description="Missing or conflicting documentation a coder should query")
    confidence: str = Field(description="high, medium or low")
