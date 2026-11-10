"""Command line entry point: validate cases, list them, run them against a model."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from . import __version__
from .grader import Grade, grade
from .providers import OpenAICompatibleProvider, OracleProvider, ProviderError, StaleProvider
from .schema import CaseError, load_cases

BASE_SYSTEM = (
    "You answer questions about Indian tax compliance. Apply the law as it stood on the date "
    "given in the question. Reply with one JSON object and nothing else."
)


def build_prompt(case: dict, skill_text: str | None = None) -> tuple[str, str]:
    system = BASE_SYSTEM
    if skill_text:
        system += "\n\nYou have this skill available. Follow it where it applies.\n\n" + skill_text
    keys = "\n".join(f'- "{key}": {description}' for key, description in case["answer_keys"].items())
    user = f"{case['question'].strip()}\n\nReturn a JSON object with exactly these keys:\n{keys}"
    return system, user


def run_cases(cases: list[dict], provider, skill_text: str | None = None) -> list[Grade]:
    grades = []
    for case in cases:
        system, user = build_prompt(case, skill_text)
        try:
            reply = provider.complete(system, user, case=case)
        except ProviderError as exc:
            grades.append(Grade(case_id=case["id"], passed=False, error=str(exc)))
            continue
        grades.append(grade(case, reply))
    return grades


def summarise(cases: list[dict], grades: list[Grade]) -> dict:
    by_id = {case["id"]: case for case in cases}
    rows = defaultdict(lambda: {"total": 0, "passed": 0, "stale": 0, "errors": 0})
    for item in grades:
        for bucket in (by_id[item.case_id]["category"], "ALL"):
            rows[bucket]["total"] += 1
            rows[bucket]["passed"] += item.passed
            rows[bucket]["stale"] += item.stale
            rows[bucket]["errors"] += item.error is not None
    return dict(rows)


def format_summary(summary: dict, title: str) -> str:
    lines = [title, f"{'category':<14}{'passed':>8}{'total':>7}{'pass %':>8}{'stale':>7}{'errors':>8}"]
    for name in sorted(key for key in summary if key != "ALL") + ["ALL"]:
        row = summary[name]
        rate = 100 * row["passed"] / row["total"] if row["total"] else 0
        lines.append(f"{name:<14}{row['passed']:>8}{row['total']:>7}{rate:>8.1f}{row['stale']:>7}{row['errors']:>8}")
    return "\n".join(lines)


def _make_provider(args):
    if args.provider == "oracle":
        return OracleProvider()
    if args.provider == "stale":
        return StaleProvider()
    if not args.model or not args.base_url:
        raise ProviderError("--model and --base-url are required for the openai provider")
    return OpenAICompatibleProvider(args.model, args.base_url, args.api_key_env)


def cmd_validate(args) -> int:
    cases = load_cases(args.cases)
    levels = defaultdict(int)
    for case in cases:
        levels[case["verification"]] += 1
    detail = ", ".join(f"{count} {level}" for level, count in sorted(levels.items()))
    print(f"{len(cases)} cases OK ({detail})")
    return 0


def cmd_list(args) -> int:
    for case in load_cases(args.cases):
        print(f"{case['id']:<44}{case['category']:<12}{case['verification']:<10}{case['title']}")
    return 0


def cmd_run(args) -> int:
    cases = load_cases(args.cases)
    if args.category:
        cases = [case for case in cases if case["category"] == args.category]
        if not cases:
            raise CaseError(f"no cases in category {args.category}")
    provider = _make_provider(args)
    output = {"version": __version__, "model": args.model or args.provider, "runs": {}}

    baseline = run_cases(cases, provider)
    output["runs"]["baseline"] = {"summary": summarise(cases, baseline), "grades": [vars(g) for g in baseline]}
    print(format_summary(output["runs"]["baseline"]["summary"], "Baseline (no skill)"))

    if args.skill:
        skill_text = Path(args.skill).read_text(encoding="utf-8")
        with_skill = run_cases(cases, provider, skill_text)
        output["runs"]["with_skill"] = {"summary": summarise(cases, with_skill), "grades": [vars(g) for g in with_skill]}
        print()
        print(format_summary(output["runs"]["with_skill"]["summary"], f"With skill: {args.skill}"))
        before = output["runs"]["baseline"]["summary"]["ALL"]["passed"]
        after = output["runs"]["with_skill"]["summary"]["ALL"]["passed"]
        print(f"\nCases passed: {before} without the skill, {after} with it ({after - before:+d}).")

    if args.out:
        Path(args.out).write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(f"\nFull results written to {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="taxbench", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--cases", default="cases", help="directory holding the case files")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("validate", help="check every case file").set_defaults(func=cmd_validate)
    commands.add_parser("list", help="list the cases").set_defaults(func=cmd_list)

    run = commands.add_parser("run", help="run the cases against a model")
    run.add_argument("--provider", choices=("openai", "oracle", "stale"), default="openai")
    run.add_argument("--model")
    run.add_argument("--base-url", help="for example https://api.openai.com/v1")
    run.add_argument("--api-key-env", default="TAXBENCH_API_KEY")
    run.add_argument("--skill", help="path to a SKILL.md to test; runs the cases with and without it")
    run.add_argument("--category")
    run.add_argument("--out", help="write full results as JSON to this file")
    run.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (CaseError, ProviderError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
