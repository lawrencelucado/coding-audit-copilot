"""Tests for the deterministic lookup tools, using small synthetic fixture files
written in the CMS file formats (no real NCCI data in the repo)."""
from datetime import date

import pytest

from copilot.icd10 import Icd10Table, dotted, normalize
from copilot.ncci import NcciTables


def order_line(order: int, code: str, billable: bool, short: str, long: str) -> str:
    return f"{order:05d} {code:<7} {'1' if billable else '0'} {short:<60} {long}\n"


@pytest.fixture
def icd10(tmp_path):
    p = tmp_path / "icd10cm_order_2026.txt"
    p.write_text("".join([
        order_line(1, "E11", False, "Type 2 diabetes mellitus", "Type 2 diabetes mellitus"),
        order_line(2, "E1165", True, "Type 2 diabetes w hyperglycemia", "Type 2 diabetes mellitus with hyperglycemia"),
        order_line(3, "E119", True, "Type 2 diabetes w/o complications", "Type 2 diabetes mellitus without complications"),
        order_line(4, "I10", True, "Essential (primary) hypertension", "Essential (primary) hypertension"),
    ]), encoding="latin-1")
    return Icd10Table.from_order_file(p, 2026)


def test_normalize_and_dot():
    assert normalize("e11.65") == "E1165"
    assert dotted("E1165") == "E11.65"
    assert dotted("I10") == "I10"


def test_lookup_billable(icd10):
    r = icd10.lookup("E11.65")
    assert r["found"] and r["billable"] and "hyperglycemia" in r["description"]


def test_lookup_header_is_not_billable_and_lists_children(icd10):
    r = icd10.lookup("E11")
    assert r["found"] and not r["billable"]
    assert "E11.65" in r["billable_children_sample"]


def test_lookup_unknown_code_is_not_guessed(icd10):
    r = icd10.lookup("E11.99")
    assert r["found"] is False and r["billable"] is False


def test_search_requires_all_terms_and_ranks_billable_first(icd10):
    hits = icd10.search("diabetes hyperglycemia")
    assert [h["code"] for h in hits] == ["E11.65"]
    assert icd10.search("diabetes")[-1]["code"] == "E11"   # header code last


@pytest.fixture
def ncci(tmp_path):
    ptp = tmp_path / "ccipra.txt"
    ptp.write_text(
        "Column 1\tColumn 2\t*\tEffective Date\tDeletion Date\tModifier\tPTP Edit Rationale\n"
        "T0001\tT0002\t\t20200101\t*\t1\tTest rationale A\n"
        "T0003\tT0004\t\t20200101\t20250101\t0\tTest rationale B\n",
        encoding="latin-1")
    mue = tmp_path / "practitioner.csv"
    mue.write_text('"Header line"\nT0001,2,2 Date of Service Edit: Policy,Test\nT0005,1,1 Line Edit,Test\n',
                   encoding="latin-1")
    t = NcciTables()
    assert t.load_ptp_file(ptp) == 2
    assert t.load_mue_file(mue) == 2
    return t


def test_ptp_edit_found_in_either_order(ncci):
    r = ncci.check_pair("T0002", "T0001", date(2026, 1, 1))
    assert r["status"] == "edit" and r["column1"] == "T0001" and r["modifier_indicator"] == "1"


def test_ptp_deleted_edit_not_active(ncci):
    assert ncci.check_pair("T0003", "T0004", date(2026, 1, 1))["status"] == "no_edit"
    assert ncci.check_pair("T0003", "T0004", date(2024, 6, 1))["status"] == "edit"


def test_mue_limits(ncci):
    assert ncci.check_units("T0001", 2)["status"] == "ok"
    over = ncci.check_units("T0001", 3)
    assert over["status"] == "exceeds" and over["mai"] == "2"
    assert ncci.check_units("T9999", 1)["status"] == "no_mue"


def test_unloaded_tables_say_unavailable():
    t = NcciTables()
    assert t.check_pair("T0001", "T0002", date(2026, 1, 1))["status"] == "unavailable"
    assert t.check_units("T0001", 1)["status"] == "unavailable"
