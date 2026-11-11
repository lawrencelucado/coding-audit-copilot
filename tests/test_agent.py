"""Agent-loop test with a scripted fake client (no API key or network needed)."""
from types import SimpleNamespace as NS

from copilot.agent import CodingAgent
from copilot.icd10 import Icd10Code, Icd10Table
from copilot.ncci import NcciTables


def usage():
    return NS(input_tokens=1000, output_tokens=200, cache_read_input_tokens=500, iterations=None)


def tool_use(id_, name, input_):
    return NS(type="tool_use", id=id_, name=name, input=input_)


class FakeMessages:
    def __init__(self, script):
        self.script, self.calls = list(script), []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.script.pop(0)


def make_agent(script):
    icd = Icd10Table({"I10": Icd10Code("I10", True, "HTN", "Essential (primary) hypertension")}, 2026)
    client = NS(beta=NS(messages=FakeMessages(script)))
    return CodingAgent(icd, NcciTables(), client=client), client.beta.messages


def test_loop_runs_tools_then_accepts_submission():
    result = {"diagnoses": [{"code": "I10", "evidence": "Essential hypertension", "sequence": 1}],
              "procedures": [{"code": "99213", "modifiers": [], "units": 1, "evidence": "MDM low"}],
              "edit_flags": [], "documentation_gaps": [], "confidence": "high"}
    agent, msgs = make_agent([
        NS(stop_reason="tool_use", usage=usage(), content=[tool_use("t1", "icd10_lookup", {"code": "I10"})]),
        NS(stop_reason="tool_use", usage=usage(), content=[tool_use("t2", "submit_coding", result)]),
    ])
    out, trace = agent.code_encounter("c1", "note", "2026-01-01")
    assert out is not None and out.diagnoses[0].code == "I10"
    assert trace.turns == 2 and [c["tool"] for c in trace.tool_calls] == ["icd10_lookup", "submit_coding"]
    assert trace.cost_usd > 0 and trace.error is None
    # The lookup result went back to the model as a tool_result.
    tool_result = msgs.calls[1]["messages"][2]["content"][0]
    assert tool_result["tool_use_id"] == "t1" and '"billable": true' in tool_result["content"]
    assert msgs.calls[0]["fallbacks"] == "default"


def test_invalid_submission_is_returned_as_error_then_fixed():
    bad = {"diagnoses": "not a list"}
    good = {"diagnoses": [], "procedures": [], "confidence": "low"}
    agent, msgs = make_agent([
        NS(stop_reason="tool_use", usage=usage(), content=[tool_use("t1", "submit_coding", bad)]),
        NS(stop_reason="tool_use", usage=usage(), content=[tool_use("t2", "submit_coding", good)]),
    ])
    out, trace = agent.code_encounter("c2", "note", "2026-01-01")
    assert out is not None and trace.turns == 2
    assert msgs.calls[1]["messages"][2]["content"][0]["is_error"] is True


def test_refusal_stops_cleanly():
    agent, _ = make_agent([NS(stop_reason="refusal", usage=usage(), content=[])])
    out, trace = agent.code_encounter("c3", "note", "2026-01-01")
    assert out is None and trace.error == "refusal"
