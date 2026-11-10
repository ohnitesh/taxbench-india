import copy
import json
from pathlib import Path

import pytest
import yaml

from taxbench.providers import OracleProvider, StaleProvider
from taxbench.runner import build_prompt, main, run_cases, summarise
from taxbench.schema import CaseError, check_case, load_cases

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"


@pytest.fixture(scope="module")
def cases():
    return load_cases(CASES_DIR)


def good_case():
    return {
        "id": "demo-case",
        "category": "demo",
        "title": "Demo",
        "question": "What is the tax?",
        "answer_keys": {"igst": "IGST in rupees"},
        "expected": {"igst": 27000},
        "sources": [{"title": "A source", "url": "https://example.org/a", "type": "official"}],
        "verification": "official",
        "as_of": "2026-11-10",
    }


def test_suite_loads_and_ids_are_unique(cases):
    assert len(cases) >= 40
    assert len({case["id"] for case in cases}) == len(cases)


def test_every_case_was_checked_against_a_source_or_a_calculation(cases):
    for case in cases:
        assert case["verification"] in ("official", "secondary", "computed"), case["id"]
        assert case["explanation"].strip(), case["id"]


def test_expected_answers_pass_the_grader(cases):
    grades = run_cases(cases, OracleProvider())
    assert all(item.passed for item in grades), [item.case_id for item in grades if not item.passed]


def test_outdated_answers_fail_and_are_flagged(cases):
    grades = {item.case_id: item for item in run_cases(cases, StaleProvider())}
    with_stale = [case["id"] for case in cases if case.get("stale_answer")]
    assert len(with_stale) >= 10
    for case_id in with_stale:
        assert not grades[case_id].passed and grades[case_id].stale, case_id
    for case in cases:
        if not case.get("stale_answer"):
            assert grades[case["id"]].passed and not grades[case["id"]].stale


def test_summary_counts(cases):
    summary = summarise(cases, run_cases(cases, OracleProvider()))
    assert summary["ALL"]["total"] == summary["ALL"]["passed"] == len(cases)
    assert sum(row["total"] for name, row in summary.items() if name != "ALL") == len(cases)


def test_prompt_lists_answer_keys_and_carries_the_skill(cases):
    system, user = build_prompt(cases[0], "SKILL BODY")
    assert "SKILL BODY" in system
    for key in cases[0]["answer_keys"]:
        assert f'"{key}"' in user
    assert "SKILL BODY" not in build_prompt(cases[0])[0]


def test_good_case_passes():
    check_case(good_case())


@pytest.mark.parametrize(
    "change,message",
    [
        (lambda c: c.pop("sources"), "missing fields"),
        (lambda c: c.update(id="Demo Case"), "lowercase"),
        (lambda c: c.update(expected={}), "non-empty"),
        (lambda c: c.update(expected={"igst": [1]}), "must be a number"),
        (lambda c: c.update(answer_keys={"cgst": "x"}), "answer_keys"),
        (lambda c: c.update(verification="trust-me"), "verification must be"),
        (lambda c: c.update(sources=[]), "at least one source"),
        (lambda c: c["sources"][0].update(url="http://example.org"), "https://"),
        (lambda c: c["sources"][0].update(type="blog"), "type"),
        (lambda c: c["sources"][0].update(type="secondary"), "needs a source with type: official"),
        (lambda c: (c.update(verification="secondary"), c["sources"][0].update(type="secondary")), "two independent sources"),
        (lambda c: c.update(verification="computed"), "reference block"),
        (lambda c: c.update(as_of="yesterday"), "must be a date"),
        (lambda c: c.update(stale_answer={"igst": 27000}), "same as expected"),
        (lambda c: c.update(stale_answer={"cgst": 1}), "keys from expected"),
        (lambda c: c.update(reference={"fn": "nope"}), "reference.fn"),
        (lambda c: c.update(reference={"fn": "gst_split", "args": {"taxable_value": 150000, "rate_percent": 12, "supplier_state": "08", "pos_state": "24"}}), "reference gives"),
        (lambda c: c.update(reference={"fn": "gst_split", "args": {"taxable_value": 1}}), "reference call failed"),
        (lambda c: c.update(reference={"fn": "eway_validity_days", "args": {"distance_km": 10, "km_per_day": 200}}), "shares no keys"),
    ],
)
def test_bad_cases_are_rejected(change, message):
    case = copy.deepcopy(good_case())
    change(case)
    with pytest.raises(CaseError, match=message):
        check_case(case)


def test_reference_block_that_agrees_is_accepted():
    case = good_case()
    case["reference"] = {"fn": "gst_split", "args": {"taxable_value": 150000, "rate_percent": 18, "supplier_state": "08", "pos_state": "24"}}
    check_case(case)


def test_file_name_and_folder_must_match(tmp_path):
    folder = tmp_path / "cases" / "demo"
    folder.mkdir(parents=True)
    (folder / "other-name.yaml").write_text(yaml.safe_dump(good_case()), encoding="utf-8")
    with pytest.raises(CaseError, match="file name must be"):
        load_cases(tmp_path / "cases")


def test_wrong_folder_is_rejected(tmp_path):
    folder = tmp_path / "cases" / "elsewhere"
    folder.mkdir(parents=True)
    (folder / "demo-case.yaml").write_text(yaml.safe_dump(good_case()), encoding="utf-8")
    with pytest.raises(CaseError, match="belongs in"):
        load_cases(tmp_path / "cases")


def test_empty_or_missing_directory(tmp_path):
    with pytest.raises(CaseError, match="no cases directory"):
        load_cases(tmp_path / "missing")
    (tmp_path / "cases").mkdir()
    with pytest.raises(CaseError, match="no case files"):
        load_cases(tmp_path / "cases")


def test_cli_validate_and_list(capsys):
    assert main(["--cases", str(CASES_DIR), "validate"]) == 0
    assert "cases OK" in capsys.readouterr().out
    assert main(["--cases", str(CASES_DIR), "list"]) == 0
    assert "eway-validity-310-km" in capsys.readouterr().out


def test_cli_run_writes_results(tmp_path, capsys):
    out = tmp_path / "results.json"
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: demo\n---\nAlways check the date.", encoding="utf-8")
    code = main(["--cases", str(CASES_DIR), "run", "--provider", "stale", "--skill", str(skill), "--out", str(out)])
    assert code == 0
    printed = capsys.readouterr().out
    assert "Baseline (no skill)" in printed and "With skill" in printed
    data = json.loads(out.read_text(encoding="utf-8"))
    assert set(data["runs"]) == {"baseline", "with_skill"}
    assert data["runs"]["baseline"]["summary"]["ALL"]["stale"] >= 10


def test_cli_reports_errors_cleanly(tmp_path, capsys):
    assert main(["--cases", str(tmp_path / "nope"), "validate"]) == 1
    assert "error:" in capsys.readouterr().err
    assert main(["--cases", str(CASES_DIR), "run", "--category", "no-such-category", "--provider", "oracle"]) == 1
    assert main(["--cases", str(CASES_DIR), "run"]) == 1  # openai provider without model or base url
