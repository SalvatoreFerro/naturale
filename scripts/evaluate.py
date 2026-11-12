#!/usr/bin/env python3
"""Validate the local pilot dataset and aggregate blinded human judgements."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys


GENRES = {"email", "summary", "message", "professional"}
SPLITS = {"development", "heldout"}
PREFERENCES = {"skill", "baseline", "tie"}
CHECK_FIELDS = {
    "preserve_exact",
    "exclude_exact",
    "reviewer_checks",
    "already_good",
    "embedded_instruction",
}


class ValidationError(ValueError):
    """An input file does not satisfy the documented evaluation schema."""


def read_jsonl(path):
    records = []
    with Path(path).open(encoding="utf-8") as source:
        for number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValidationError(f"{path}:{number}: invalid JSON: {error.msg}") from error
            if not isinstance(item, dict):
                raise ValidationError(f"{path}:{number}: expected a JSON object")
            records.append((number, item))
    return records


def require_text(value, location):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{location}: expected a nonempty string")


def validate_cases(path):
    cases = {}
    distribution = Counter()
    good_examples = Counter()
    injection_examples = Counter()
    required = {"id", "split", "genre", "operation", "instruction", "text", "checks"}
    for number, item in read_jsonl(path):
        location = f"{path}:{number}"
        if set(item) != required:
            raise ValidationError(f"{location}: fields must be {sorted(required)}")
        for field in ("id", "split", "genre", "operation", "instruction", "text"):
            require_text(item[field], f"{location}.{field}")
        if item["id"] in cases:
            raise ValidationError(f"{location}: duplicate case id {item['id']!r}")
        if item["split"] not in SPLITS or item["genre"] not in GENRES:
            raise ValidationError(f"{location}: unknown split or genre")
        expected_operation = "summarize" if item["genre"] == "summary" else "rewrite"
        if item["operation"] != expected_operation:
            raise ValidationError(f"{location}: expected operation {expected_operation!r}")
        checks = item["checks"]
        if not isinstance(checks, dict) or set(checks) != CHECK_FIELDS:
            raise ValidationError(f"{location}.checks: fields must be {sorted(CHECK_FIELDS)}")
        for field in ("preserve_exact", "exclude_exact", "reviewer_checks"):
            if not isinstance(checks[field], list):
                raise ValidationError(f"{location}.checks.{field}: expected a list")
            for value in checks[field]:
                require_text(value, f"{location}.checks.{field}")
            if len(set(checks[field])) != len(checks[field]):
                raise ValidationError(f"{location}.checks.{field}: duplicate check")
        if not checks["reviewer_checks"]:
            raise ValidationError(f"{location}: at least one human fidelity check is required")
        for field in ("already_good", "embedded_instruction"):
            if type(checks[field]) is not bool:
                raise ValidationError(f"{location}.checks.{field}: expected a boolean")
        for literal in checks["preserve_exact"]:
            if literal not in item["text"]:
                raise ValidationError(f"{location}: preserve_exact value absent from source: {literal!r}")
        if set(checks["preserve_exact"]) & set(checks["exclude_exact"]):
            raise ValidationError(f"{location}: conflicting exact checks")
        bucket = (item["genre"], item["split"])
        distribution[bucket] += 1
        good_examples[bucket] += checks["already_good"]
        injection_examples[bucket] += checks["embedded_instruction"]
        cases[item["id"]] = item
    if len(cases) != 80:
        raise ValidationError(f"{path}: expected 80 cases, found {len(cases)}")
    for genre in sorted(GENRES):
        for split in sorted(SPLITS):
            bucket = (genre, split)
            if distribution[bucket] != 10:
                raise ValidationError(f"{path}: expected 10 cases for {genre}/{split}")
            if not good_examples[bucket] or not injection_examples[bucket]:
                raise ValidationError(f"{path}: {genre}/{split} needs already-good and injection examples")
    return cases


def aggregate_votes(path, cases):
    heldout = {case_id for case_id, item in cases.items() if item["split"] == "heldout"}
    reviewers = defaultdict(set)
    seen = set()
    preferences = Counter()
    critical_errors = 0
    required = {"case_id", "reviewer_id", "preference", "critical_error"}
    if path is not None:
        for number, item in read_jsonl(path):
            location = f"{path}:{number}"
            if set(item) != required:
                raise ValidationError(f"{location}: fields must be {sorted(required)}")
            for field in ("case_id", "reviewer_id", "preference"):
                require_text(item[field], f"{location}.{field}")
            if item["case_id"] not in heldout:
                raise ValidationError(f"{location}: votes must refer to a known heldout case")
            if item["preference"] not in PREFERENCES:
                raise ValidationError(f"{location}: preference must be skill, baseline, or tie")
            if type(item["critical_error"]) is not bool:
                raise ValidationError(f"{location}.critical_error: expected a boolean")
            pair = (item["case_id"], item["reviewer_id"])
            if pair in seen:
                raise ValidationError(f"{location}: duplicate case/reviewer vote {pair!r}")
            seen.add(pair)
            reviewers[item["case_id"]].add(item["reviewer_id"])
            preferences[item["preference"]] += 1
            critical_errors += item["critical_error"]
    n_ratings = sum(preferences.values())
    score = ((preferences["skill"] + 0.5 * preferences["tie"]) / n_ratings) if n_ratings else None
    missing = sorted(case_id for case_id in heldout if len(reviewers[case_id]) < 2)
    passed = n_ratings > 0 and score > 0.60 and critical_errors == 0 and not missing
    return {
        "dataset_valid": True,
        "total_cases": len(cases),
        "heldout_cases": len(heldout),
        "n_ratings": n_ratings,
        "n_cases": sum(bool(value) for value in reviewers.values()),
        "skill_preference": score,
        "critical_errors": critical_errors,
        "cases_needing_reviews": missing,
        "status": "passed" if passed else "not_validated",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-cases", required=True, metavar="PATH", help="Validate the 80-case JSONL pilot dataset")
    parser.add_argument("--votes", metavar="PATH", help="Optional JSONL votes for heldout cases only")
    args = parser.parse_args(argv)
    try:
        cases = validate_cases(args.validate_cases)
        result = aggregate_votes(args.votes, cases)
    except (ValidationError, OSError, UnicodeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
