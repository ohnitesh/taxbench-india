import pytest

from taxbench.grader import extract_json, grade, values_match

CASE = {
    "id": "demo",
    "expected": {"tds_amount": 0, "rate_percent": 0},
    "stale_answer": {"tds_amount": 4500, "rate_percent": 10},
}


def test_extract_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_from_code_fence_and_prose():
    reply = 'Here is the answer:\n```json\n{"cgst": 500, "note": "half {each}"}\n```\nHope that helps.'
    assert extract_json(reply) == {"cgst": 500, "note": "half {each}"}


def test_extract_skips_braces_that_are_not_json():
    assert extract_json('Using the set {x} we get {"a": 2}') == {"a": 2}


@pytest.mark.parametrize("reply", ["", "   ", "no json here", "[1, 2, 3]", None])
def test_extract_fails_without_an_object(reply):
    with pytest.raises(ValueError):
        extract_json(reply)


@pytest.mark.parametrize(
    "expected,actual,ok",
    [
        (500, 500, True),
        (500, 500.004, True),
        (500, 500.5, False),
        (500, "500", True),
        (27000, "Rs. 27,000", True),
        (27000, "₹27,000.00", True),
        (18, "18%", True),
        (500, None, False),
        (500, "five hundred", False),
        (0, False, False),  # a boolean is not a number
        (True, True, True),
        (True, "Yes", True),
        (False, "not required", True),
        (True, 1, False),
        (True, "maybe", False),
        ("393", " 393 ", True),
        ("IGST", "igst", True),
        ("IGST", 5, False),
    ],
)
def test_values_match(expected, actual, ok):
    assert values_match(expected, actual) is ok


def test_grade_pass():
    result = grade(CASE, '{"tds_amount": 0, "rate_percent": 0}')
    assert result.passed and not result.stale and not result.mismatches


def test_grade_flags_outdated_answer():
    result = grade(CASE, '{"tds_amount": 4500, "rate_percent": 10}')
    assert not result.passed and result.stale
    assert result.mismatches["tds_amount"] == {"expected": 0, "got": 4500}


def test_grade_wrong_but_not_outdated():
    result = grade(CASE, '{"tds_amount": 900, "rate_percent": 2}')
    assert not result.passed and not result.stale


def test_grade_missing_key_fails():
    result = grade(CASE, '{"tds_amount": 0}')
    assert not result.passed and "rate_percent" in result.mismatches


def test_grade_extra_keys_are_ignored():
    assert grade(CASE, '{"tds_amount": 0, "rate_percent": 0, "reasoning": "under the limit"}').passed


def test_grade_unparseable_reply_is_an_error():
    result = grade(CASE, "I think no tax is due.")
    assert not result.passed and result.error


def test_grade_respects_case_tolerance():
    case = {"id": "t", "expected": {"x": 100}, "tolerance": {"x": 1}}
    assert grade(case, '{"x": 100.9}').passed
    assert not grade(case, '{"x": 101.5}').passed
