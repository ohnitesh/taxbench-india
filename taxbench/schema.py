"""Load case files and check them before they are allowed into the suite."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import yaml

from .grader import values_match
from .reference import FUNCTIONS

VERIFICATION_LEVELS = ("official", "secondary", "computed")
SOURCE_TYPES = ("official", "secondary")
REQUIRED = ("id", "category", "title", "question", "answer_keys", "expected", "sources", "verification", "as_of")
_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_SCALAR = (bool, int, float, str)


class CaseError(ValueError):
    pass


def _as_date(value, label: str) -> dt.date:
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as exc:
        raise CaseError(f"{label} must be a date like 2026-11-10") from exc


def check_case(case: dict, path: Path | None = None) -> None:
    """Raise CaseError when a case breaks the rules in CONTRIBUTING.md."""
    if not isinstance(case, dict):
        raise CaseError("case file must contain one mapping")
    missing = [key for key in REQUIRED if key not in case]
    if missing:
        raise CaseError(f"missing fields: {', '.join(missing)}")

    case_id = case["id"]
    if not isinstance(case_id, str) or not _ID.match(case_id):
        raise CaseError("id must be lowercase words joined by hyphens")
    if path is not None:
        if path.stem != case_id:
            raise CaseError(f"file name must be {case_id}.yaml")
        if path.parent.name != case["category"]:
            raise CaseError(f"case belongs in cases/{case['category']}/")

    expected = case["expected"]
    if not isinstance(expected, dict) or not expected:
        raise CaseError("expected must be a non-empty mapping")
    for key, value in expected.items():
        if not isinstance(value, _SCALAR):
            raise CaseError(f"expected.{key} must be a number, true/false or text")

    answer_keys = case["answer_keys"]
    if not isinstance(answer_keys, dict) or set(answer_keys) != set(expected):
        raise CaseError("answer_keys must describe exactly the keys in expected")

    if case["verification"] not in VERIFICATION_LEVELS:
        raise CaseError(f"verification must be one of {VERIFICATION_LEVELS}")
    sources = case["sources"]
    if not isinstance(sources, list) or not sources:
        raise CaseError("at least one source is required")
    for source in sources:
        if not isinstance(source, dict) or not source.get("title") or not source.get("url"):
            raise CaseError("each source needs a title and a url")
        if source.get("type") not in SOURCE_TYPES:
            raise CaseError(f"each source needs type: one of {SOURCE_TYPES}")
        if not str(source["url"]).startswith("https://"):
            raise CaseError("source urls must start with https://")
    kinds = [source["type"] for source in sources]
    if case["verification"] == "official" and "official" not in kinds:
        raise CaseError("verification: official needs a source with type: official")
    if case["verification"] == "secondary" and len(sources) < 2:
        raise CaseError("verification: secondary needs two independent sources")
    if case["verification"] == "computed" and "reference" not in case:
        raise CaseError("verification: computed needs a reference block")

    _as_date(case["as_of"], "as_of")
    if "law_effective_from" in case:
        _as_date(case["law_effective_from"], "law_effective_from")

    stale = case.get("stale_answer")
    if stale is not None:
        if not isinstance(stale, dict) or not stale or not set(stale) <= set(expected):
            raise CaseError("stale_answer must use keys from expected")
        if all(values_match(expected[key], value) for key, value in stale.items()):
            raise CaseError("stale_answer is the same as expected")

    reference = case.get("reference")
    if reference is not None:
        check_reference(case)


def check_reference(case: dict) -> None:
    """Recompute the expected answer with the reference calculators."""
    reference = case["reference"]
    name = reference.get("fn")
    if name not in FUNCTIONS:
        raise CaseError(f"reference.fn must be one of {sorted(FUNCTIONS)}")
    try:
        computed = FUNCTIONS[name](**(reference.get("args") or {}))
    except (TypeError, ValueError) as exc:
        raise CaseError(f"reference call failed: {exc}") from exc
    shared = set(computed) & set(case["expected"])
    if not shared:
        raise CaseError("reference result shares no keys with expected")
    for key in sorted(shared):
        if not values_match(case["expected"][key], computed[key]):
            raise CaseError(f"expected.{key} is {case['expected'][key]!r} but the reference gives {computed[key]!r}")


def load_cases(root: str | Path = "cases") -> list[dict]:
    """Load and check every case under ``root``. Raises on the first bad file."""
    root = Path(root)
    if not root.is_dir():
        raise CaseError(f"no cases directory at {root}")
    cases, seen = [], {}
    for path in sorted(root.glob("*/*.yaml")):
        with path.open(encoding="utf-8") as handle:
            case = yaml.safe_load(handle)
        try:
            check_case(case, path)
        except CaseError as exc:
            raise CaseError(f"{path}: {exc}") from exc
        if case["id"] in seen:
            raise CaseError(f"{path}: id already used by {seen[case['id']]}")
        seen[case["id"]] = path
        cases.append(case)
    if not cases:
        raise CaseError(f"no case files found under {root}")
    return cases
