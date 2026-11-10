"""Deterministic grading. No judge model: an answer either matches or it does not."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

DEFAULT_TOLERANCE = 0.01
_TRUE = {"true", "yes", "y", "required", "applicable"}
_FALSE = {"false", "no", "n", "not required", "not applicable"}


@dataclass
class Grade:
    case_id: str
    passed: bool
    stale: bool = False
    error: str | None = None
    mismatches: dict = field(default_factory=dict)
    answer: dict | None = None


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply, tolerating code fences and prose."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty reply")
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("no JSON object found in reply")


def _to_number(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"(?i)rs\.?|inr|₹|,|%|\s", "", value)
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _to_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
    return None


def values_match(expected, actual, tolerance: float = DEFAULT_TOLERANCE) -> bool:
    if isinstance(expected, bool):
        return _to_bool(actual) is expected
    if isinstance(expected, (int, float)):
        number = _to_number(actual)
        return number is not None and abs(number - float(expected)) <= tolerance
    if isinstance(expected, str):
        return isinstance(actual, str) and actual.strip().casefold() == expected.strip().casefold()
    return expected == actual


def _matches_all(target: dict, answer: dict, tolerances: dict) -> dict:
    """Return the keys that do not match, mapped to (expected, got)."""
    wrong = {}
    for key, expected in target.items():
        got = answer.get(key)
        if not values_match(expected, got, tolerances.get(key, DEFAULT_TOLERANCE)):
            wrong[key] = {"expected": expected, "got": got}
    return wrong


def grade(case: dict, reply: str) -> Grade:
    """Grade one reply against one case.

    A case passes only when every expected key matches. ``stale`` is set when
    the reply fails and matches the case's ``stale_answer``, which records what
    the rule used to be before it changed.
    """
    try:
        answer = extract_json(reply)
    except ValueError as exc:
        return Grade(case_id=case["id"], passed=False, error=str(exc))
    tolerances = case.get("tolerance") or {}
    wrong = _matches_all(case["expected"], answer, tolerances)
    stale = False
    stale_answer = case.get("stale_answer")
    if wrong and stale_answer:
        stale = not _matches_all(stale_answer, answer, tolerances)
    return Grade(case_id=case["id"], passed=not wrong, stale=stale, mismatches=wrong, answer=answer)
