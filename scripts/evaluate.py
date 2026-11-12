#!/usr/bin/env python3
"""Validate local evaluation data, prepare blinded comparisons, aggregate human votes."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import json
import os
from pathlib import Path
import random
import secrets
import shutil
import stat
import sys

GENRES = {"email", "summary", "message", "professional"}
SPLITS = {"development", "heldout"}
PREFERENCES = {"skill", "baseline", "tie"}
CHECK_FIELDS = {"preserve_exact", "exclude_exact", "reviewer_checks", "already_good", "embedded_instruction"}
MINIMUM_HELDOUT = 40
MAX_JSONL_BYTES = 20 * 1024 * 1024


class ValidationError(ValueError):
    """An input file does not satisfy the documented evaluation schema."""


def read_jsonl(path):
    records = []
    source_path = Path(path).expanduser()
    if source_path.is_symlink() or not stat.S_ISREG(source_path.lstat().st_mode):
        raise ValidationError(f"{path}: expected a regular file, not a symlink or special file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(source_path, flags)
    with os.fdopen(fd, "rb") as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValidationError(f"{path}: expected a regular file")
        raw = source.read(MAX_JSONL_BYTES + 1)
    if len(raw) > MAX_JSONL_BYTES:
        raise ValidationError(f"{path}: JSONL exceeds 20 MiB")
    # JSONL separa record con LF; U+2028/U+0085 possono far parte di una stringa.
    for number, line in enumerate(raw.decode("utf-8-sig").split("\n"), start=1):
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


def _validate_provenance(value, location):
    if not isinstance(value, dict) or value.get("kind") not in {"synthetic", "human_authorized"}:
        raise ValidationError(f"{location}: expected kind synthetic or human_authorized")
    if value["kind"] == "synthetic":
        if set(value) != {"kind"}:
            raise ValidationError(f"{location}: synthetic examples must not claim human consent")
    elif set(value) != {"kind", "consent", "anonymized"} or value.get("consent") != "confirmed" or value.get("anonymized") is not True:
        raise ValidationError(f"{location}: human data requires consent=confirmed and anonymized=true")


def validate_cases(path, pilot=False):
    """Validate the extensible format; --pilot separately checks the original 80 cases."""
    cases = {}
    required = {"id", "split", "genre", "operation", "instruction", "text", "checks"}
    for number, item in read_jsonl(path):
        location = f"{path}:{number}"
        if not required <= item.keys() or item.keys() - required - {"provenance"}:
            raise ValidationError(f"{location}: expected {sorted(required)} and optional provenance")
        for field in ("id", "split", "genre", "operation", "instruction", "text"):
            require_text(item[field], f"{location}.{field}")
        if item["id"] in cases:
            raise ValidationError(f"{location}: duplicate case id {item['id']!r}")
        if item["split"] not in SPLITS or item["genre"] not in GENRES:
            raise ValidationError(f"{location}: unknown split or genre")
        expected_operation = "summarize" if item["genre"] == "summary" else "rewrite"
        if item["operation"] != expected_operation:
            raise ValidationError(f"{location}: expected operation {expected_operation!r}")
        if "provenance" in item:
            _validate_provenance(item["provenance"], f"{location}.provenance")
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
        cases[item["id"]] = item
    if not cases or not any(item["split"] == "heldout" for item in cases.values()):
        raise ValidationError(f"{path}: at least one case and one heldout case are required")
    if pilot:
        validate_pilot(cases, path)
    return cases


def validate_pilot(cases, location="dataset"):
    """The original pilot's composition is a policy, not the JSONL format."""
    if len(cases) != 80:
        raise ValidationError(f"{location}: pilot expects 80 cases, found {len(cases)}")
    for genre in sorted(GENRES):
        for split in sorted(SPLITS):
            bucket = [item for item in cases.values() if item["genre"] == genre and item["split"] == split]
            if len(bucket) != 10:
                raise ValidationError(f"{location}: pilot expects 10 cases for {genre}/{split}")
            if not any(item["checks"]["already_good"] for item in bucket) or not any(item["checks"]["embedded_instruction"] for item in bucket):
                raise ValidationError(f"{location}: {genre}/{split} needs already-good and injection examples")


def aggregate_votes(path, cases):
    heldout = {case_id for case_id, item in cases.items() if item["split"] == "heldout"}
    reviewers = defaultdict(set)
    per_case = defaultdict(Counter)
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
            per_case[item["case_id"]][item["preference"]] += 1
            critical_errors += item["critical_error"]
    n_ratings = sum(preferences.values())
    pooled = Fraction(2 * preferences["skill"] + preferences["tie"], 2 * n_ratings) if n_ratings else None
    case_scores = [Fraction(2 * votes["skill"] + votes["tie"], 2 * sum(votes.values())) for votes in per_case.values()]
    macro = sum(case_scores, Fraction(0)) / len(case_scores) if case_scores else None
    missing = sorted(case_id for case_id in heldout if len(reviewers[case_id]) < 2)
    sample_sufficient = len(heldout) >= MINIMUM_HELDOUT
    passed = macro is not None and macro > Fraction(3, 5) and critical_errors == 0 and not missing and sample_sufficient
    provenance = Counter(item.get("provenance", {"kind": "synthetic"})["kind"] for item in cases.values())
    return {
        "dataset_valid": True, "total_cases": len(cases), "heldout_cases": len(heldout),
        "n_ratings": n_ratings, "n_cases": len(per_case),
        # Legacy field retains its vote-weighted meaning for consumers of v0.1.
        "skill_preference": float(pooled) if pooled is not None else None,
        "vote_weighted_preference": float(pooled) if pooled is not None else None,
        "case_mean_preference": float(macro) if macro is not None else None,
        "decision_metric": "case_mean_preference", "minimum_heldout_cases": MINIMUM_HELDOUT,
        "sample_sufficient": sample_sufficient, "critical_errors": critical_errors,
        "cases_needing_reviews": missing, "provenance_declarations": dict(provenance),
        "authorization_check": "declarations_only", "evaluation_scope": "preliminary_sample_only",
        "status": "passed" if passed else "not_validated",
    }


def _write_private(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def prepare_comparison(path, cases, output_dir, seed=None):
    """Prepare human-review material only; never generate outputs or call a model."""
    heldout = {case_id: item for case_id, item in cases.items() if item["split"] == "heldout"}
    required = {"case_id", "model", "skill_version", "skill_output", "baseline_output"}
    pairs = {}
    for number, item in read_jsonl(path):
        location = f"{path}:{number}"
        if set(item) != required:
            raise ValidationError(f"{location}: expected fields {sorted(required)}")
        for field in required:
            require_text(item[field], f"{location}.{field}")
        case_id = item["case_id"]
        if case_id not in heldout or case_id in pairs:
            raise ValidationError(f"{location}: unknown, non-heldout or duplicate case {case_id!r}")
        pairs[case_id] = item
    if set(pairs) != set(heldout):
        raise ValidationError("Comparison must cover every heldout case exactly once")
    if len({(item["model"], item["skill_version"]) for item in pairs.values()}) != 1:
        raise ValidationError("Use one model version and one skill version per comparison")
    if seed is None:
        seed = secrets.randbits(64)
    if type(seed) is not int or not 0 <= seed < 2 ** 64:
        raise ValidationError("Seed must be an integer from 0 to 2**64-1")
    assignments = [True] * (len(pairs) // 2) + [False] * (len(pairs) - len(pairs) // 2)
    random.Random(seed).shuffle(assignments)
    packets, mapping = [], []
    for case_id, skill_is_a in zip(sorted(pairs), assignments):
        case, pair = heldout[case_id], pairs[case_id]
        labels = {"A": "skill" if skill_is_a else "baseline", "B": "baseline" if skill_is_a else "skill"}
        packets.append({
            "case_id": case_id, "instruction": case["instruction"], "text": case["text"],
            "A": pair[labels["A"] + "_output"], "B": pair[labels["B"] + "_output"],
            "checks": case["checks"],
        })
        mapping.append({"case_id": case_id, "labels": labels, "model": pair["model"], "skill_version": pair["skill_version"]})
    destination = Path(output_dir).expanduser().absolute()
    destination = destination.parent.resolve() / destination.name
    if os.path.lexists(destination):
        raise ValidationError("Comparison output directory already exists; nothing overwritten")
    if not destination.parent.is_dir():
        raise ValidationError("Comparison output parent directory does not exist")
    destination.mkdir(mode=0o700)
    identity = (destination.stat().st_dev, destination.stat().st_ino)
    try:
        _write_private(destination / "packets.jsonl", "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in packets))
        private = {"schema_version": "1.0", "seed": seed, "mapping": mapping}
        _write_private(destination / "mapping-private.json", json.dumps(private, ensure_ascii=False, indent=2) + "\n")
    except Exception:
        if not destination.is_symlink() and destination.is_dir() and (destination.stat().st_dev, destination.stat().st_ino) == identity:
            shutil.rmtree(destination)
        raise
    return {"status": "prepared", "case_count": len(packets),
            "packet_file": str(destination / "packets.jsonl"), "private_mapping_file": str(destination / "mapping-private.json"),
            "warning": "Share packets only with authorized reviewers; keep the mapping private until votes are locked. No evaluation has been performed."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-cases", required=True, metavar="PATH", help="Validate the extensible JSONL case format")
    parser.add_argument("--pilot", action="store_true", help="Also require the original balanced 80-case pilot composition")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--votes", metavar="PATH", help="JSONL human votes for heldout cases")
    mode.add_argument("--prepare-comparison", metavar="PATH", help="JSONL outputs generated beforehand, without checks or labels")
    parser.add_argument("--output-dir", metavar="NEW_DIRECTORY", help="New local directory for blinded review packets")
    parser.add_argument("--seed", type=int, help="Optional reproducible assignment seed; kept in the private mapping")
    args = parser.parse_args(argv)
    if args.prepare_comparison and not args.output_dir:
        parser.error("--prepare-comparison requires --output-dir")
    if not args.prepare_comparison and (args.output_dir is not None or args.seed is not None):
        parser.error("--output-dir and --seed require --prepare-comparison")
    try:
        cases = validate_cases(args.validate_cases, pilot=args.pilot)
        result = prepare_comparison(args.prepare_comparison, cases, args.output_dir, args.seed) if args.prepare_comparison else aggregate_votes(args.votes, cases)
    except (ValidationError, OSError, UnicodeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
