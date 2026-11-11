"""Coding Audit Copilot agent: Claude + deterministic coding tools.

Design rule: the model reasons, the tools decide anything that must be exact.
Every code is validated against the fiscal-year ICD-10-CM file, every
procedure pair against NCCI PTP edits and every unit count against MUEs.
The result is a proposal for a certified coder, never a final claim.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date

import anthropic
from pydantic import ValidationError

from . import config
from .icd10 import Icd10Table
from .ncci import NcciTables
from .schema import CodingResult

# Claude Opus 5.5 list prices, USD per million tokens.
PRICE_IN, PRICE_OUT, PRICE_CACHE_READ = 4.00, 20.00, 0.20

SYSTEM_PROMPT = """You are a professional-fee coding assistant working for a certified coder (CPC).
You propose ICD-10-CM and CPT/HCPCS codes for one outpatient encounter; the coder makes the final decision.

How to work:
- Code only what the note documents. Every code needs an exact supporting phrase from the note as evidence.
- Follow ICD-10-CM Official Guidelines for outpatient services: code to the highest specificity documented, do not code "probable/suspected" conditions (code the signs or symptoms), and apply combination codes and presumed causal links the guidelines require (for example hypertension with heart disease or with chronic kidney disease).
- Before you submit any ICD-10-CM code, confirm it with icd10_lookup for the encounter's fiscal year. Never submit a code the lookup did not confirm as billable. Use icd10_search when you need to find the right code.
- Check every pair of procedure codes on the claim with ncci_ptp_check, and every procedure's units with mue_check. Report each edit you find in edit_flags, including whether a modifier can bypass it.
- If documentation is missing, vague or conflicting, list it in documentation_gaps instead of guessing.
- When you are done, call submit_coding exactly once with your full result. Do not write the answer as plain text."""

TOOLS = [
    {
        "name": "icd10_lookup",
        "description": "Validate one ICD-10-CM code against the official CMS file for the configured fiscal year. Returns whether it exists, whether it is billable, and its description.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "ICD-10-CM code, with or without the dot"}},
            "required": ["code"],
            "additionalProperties": False,
        },
    },
    {
        "name": "icd10_search",
        "description": "Keyword search of ICD-10-CM long descriptions. All words must appear. Returns up to 15 codes, billable codes first.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Words to match, e.g. 'type 2 diabetes hyperglycemia'"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ncci_ptp_check",
        "description": "Check whether two CPT/HCPCS codes have an active Medicare NCCI procedure-to-procedure edit on the date of service, and whether a modifier is allowed.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "code_a": {"type": "string"},
                "code_b": {"type": "string"},
                "date_of_service": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["code_a", "code_b", "date_of_service"],
            "additionalProperties": False,
        },
    },
    {
        "name": "mue_check",
        "description": "Check units of service for one CPT/HCPCS code against the Medicare practitioner Medically Unlikely Edit.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string"}, "units": {"type": "integer"}},
            "required": ["code", "units"],
            "additionalProperties": False,
        },
    },
    {
        "name": "submit_coding",
        "description": "Submit the final coding proposal. Call exactly once, at the end.",
        "input_schema": CodingResult.model_json_schema(),
    },
]


@dataclass
class RunTrace:
    """Per-encounter telemetry: what an LLMOps dashboard would chart."""
    case_id: str
    model: str
    turns: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    latency_s: float = 0.0
    stop_reason: str = ""
    fallback_used: bool = False
    error: str | None = None

    @property
    def cost_usd(self) -> float:
        return round((self.input_tokens * PRICE_IN + self.output_tokens * PRICE_OUT
                      + self.cache_read_tokens * PRICE_CACHE_READ) / 1_000_000, 5)

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["cost_usd"] = self.cost_usd
        return d


class CodingAgent:
    def __init__(self, icd10: Icd10Table, ncci: NcciTables, client: anthropic.Anthropic | None = None):
        self.icd10 = icd10
        self.ncci = ncci
        self.client = client or anthropic.Anthropic()

    # ---------- deterministic tools ----------
    def _run_tool(self, name: str, args: dict) -> str:
        if name == "icd10_lookup":
            return json.dumps(self.icd10.lookup(args["code"]))
        if name == "icd10_search":
            return json.dumps(self.icd10.search(args["query"]))
        if name == "ncci_ptp_check":
            dos = date.fromisoformat(args["date_of_service"])
            return json.dumps(self.ncci.check_pair(args["code_a"], args["code_b"], dos))
        if name == "mue_check":
            return json.dumps(self.ncci.check_units(args["code"], int(args["units"])))
        raise ValueError(f"Unknown tool {name}")

    # ---------- agent loop ----------
    def code_encounter(self, case_id: str, note: str, date_of_service: str) -> tuple[CodingResult | None, RunTrace]:
        trace = RunTrace(case_id=case_id, model=config.MODEL)
        messages: list = [{"role": "user", "content":
                           f"Date of service: {date_of_service}\n"
                           f"ICD-10-CM fiscal year loaded: FY{self.icd10.fiscal_year}\n\n"
                           f"<clinical_note>\n{note}\n</clinical_note>"}]
        start = time.perf_counter()
        result: CodingResult | None = None

        for _ in range(config.MAX_TURNS):
            response = self.client.beta.messages.create(
                model=config.MODEL,
                max_tokens=16000,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                tools=TOOLS,
                messages=messages,
                output_config={"effort": config.EFFORT},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            trace.turns += 1
            u = response.usage
            trace.input_tokens += u.input_tokens or 0
            trace.output_tokens += u.output_tokens or 0
            trace.cache_read_tokens += getattr(u, "cache_read_input_tokens", 0) or 0
            if any(getattr(it, "type", "") == "fallback_message" for it in (getattr(u, "iterations", None) or [])):
                trace.fallback_used = True
            trace.stop_reason = response.stop_reason or ""

            if response.stop_reason == "refusal":
                trace.error = "refusal"
                break
            # Keep full content (including thinking blocks) so the conversation stays valid.
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason == "pause_turn":
                continue

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                trace.error = "finished without calling submit_coding"
                break

            results = []
            for block in tool_uses:
                trace.tool_calls.append({"tool": block.name, "input": block.input})
                if block.name == "submit_coding":
                    try:
                        result = CodingResult.model_validate(block.input)
                        results.append({"type": "tool_result", "tool_use_id": block.id, "content": "Submitted."})
                    except ValidationError as exc:
                        results.append({"type": "tool_result", "tool_use_id": block.id, "is_error": True,
                                        "content": f"Invalid result, fix and resubmit: {exc}"})
                    continue
                try:
                    out = self._run_tool(block.name, block.input)
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
                except Exception as exc:  # report tool errors to the model instead of crashing
                    results.append({"type": "tool_result", "tool_use_id": block.id, "is_error": True,
                                    "content": f"{type(exc).__name__}: {exc}"})
            messages.append({"role": "user", "content": results})
            if result is not None:
                break
        else:
            trace.error = f"hit max turns ({config.MAX_TURNS})"

        trace.latency_s = round(time.perf_counter() - start, 2)
        return result, trace


def load_tables() -> tuple[Icd10Table, NcciTables]:
    order = config.icd10_order_file()
    if order is None:
        raise SystemExit(f"ICD-10-CM order file for FY{config.ICD10_FY} not found under {config.DATA_DIR}. "
                         "See README > Data setup.")
    icd10 = Icd10Table.from_order_file(order, config.ICD10_FY)
    ncci = NcciTables()
    for p in config.ptp_files():
        ncci.load_ptp_file(p)
    if (m := config.mue_file()) is not None:
        ncci.load_mue_file(m)
    return icd10, ncci
