#!/usr/bin/env python3
"""Diagnosi locale di Naturale: legge strumenti e installazioni senza modificarli."""
from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from urllib.parse import unquote, urlsplit

HOSTS = {"claude": ".claude", "codex": ".agents"}
MAX_DOCUMENT_BYTES = 1024 * 1024
EXIFTOOL_TIMEOUT = 10
VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\Z")


def _read_text(path: Path) -> str:
    """Rifiuta link, FIFO e documenti troppo grandi senza seguirli o bloccare."""
    if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("not_regular")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("not_regular")
        data = stream.read(MAX_DOCUMENT_BYTES + 1)
    if len(data) > MAX_DOCUMENT_BYTES:
        raise ValueError("too_large")
    return data.decode("utf-8")


def _has_symlink(root: Path, target: Path) -> bool:
    current = root
    for part in target.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _host_report(host: str, home: Path) -> dict:
    directory = home / HOSTS[host] / "skills" / "naturale"
    report = {"host": host, "version": None, "text_ready": False,
              "missing": [], "warnings": [], "receipt": "absent"}
    if _has_symlink(home, directory):
        report["missing"].append("unsafe_installation")
        return report
    if not directory.is_dir():
        report["missing"].append("skill_not_installed")
        return report
    try:
        text = _read_text(directory / "SKILL.md")
    except (OSError, UnicodeError, ValueError):
        report["missing"].append("skill_unreadable")
        return report
    frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.S)
    if not frontmatter or not re.search(
            r"(?m)^name:\s*['\"]?naturale['\"]?\s*$", frontmatter.group(1)):
        report["missing"].append("invalid_skill_name")
    if not frontmatter or not re.search(r"(?m)^description:\s*\S", frontmatter.group(1)):
        report["missing"].append("missing_skill_description")
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
        try:
            parsed = urlsplit(target.strip().strip("<>"))
        except ValueError:
            report["missing"].append("unsafe_reference")
            continue
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        reference = directory / unquote(parsed.path)
        try:
            reference.resolve().relative_to(directory.resolve())
            if _has_symlink(directory, reference):
                raise ValueError("symlink")
        except ValueError:
            report["missing"].append("unsafe_reference")
            continue
        try:
            if reference.is_symlink() or not stat.S_ISREG(reference.lstat().st_mode):
                raise ValueError("not_regular")
        except (OSError, ValueError):
            report["missing"].append("missing_reference")
    version_path = directory / "VERSION"
    if not os.path.lexists(version_path):
        report["version"] = "0.1.0"
    else:
        try:
            version = _read_text(version_path).strip()
            if not VERSION_PATTERN.fullmatch(version):
                raise ValueError("invalid_version")
            report["version"] = version
        except (OSError, UnicodeError, ValueError):
            report["missing"].append("invalid_version")
    receipt_path = directory / ".naturale-install.json"
    if os.path.lexists(receipt_path):
        try:
            receipt = json.loads(_read_text(receipt_path))
            if not isinstance(receipt, dict) or receipt.get("schema_version") != "1.0":
                raise ValueError("invalid_receipt")
            report["receipt"] = "present"
        except (OSError, UnicodeError, ValueError):
            report["receipt"] = "unreadable"
            report["warnings"].append("receipt_unreadable")
    else:
        report["warnings"].append("receipt_absent")
    report["missing"] = sorted(set(report["missing"]))
    report["text_ready"] = not report["missing"]
    return report


def _package_version(distribution: str) -> str | None:
    try:
        version = metadata.version(distribution)
    except (metadata.PackageNotFoundError, OSError, ValueError):
        return None
    # I metadati locali non devono poter iniettare path o testo arbitrario nel JSON.
    return version if len(version) <= 80 and re.fullmatch(r"\d+(?:\.\d+)+(?:[0-9A-Za-z.+!_-]*)", version) else None


def _exiftool_report() -> dict:
    result = {"available": False, "version": None, "problem": None}
    executable = shutil.which("exiftool")
    if not executable:
        result["problem"] = "not_found"
        return result
    try:
        completed = subprocess.run(
            [executable, "-config", "", "-ver"], capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=EXIFTOOL_TIMEOUT,
            check=False, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        result["problem"] = "not_executable_or_timeout"
        return result
    version = completed.stdout.strip()
    if completed.returncode or not re.fullmatch(r"\d+(?:\.\d+){1,2}", version):
        result["problem"] = "version_check_failed"
        return result
    result.update(available=True, version=version)
    return result


def doctor(host: str = "both", home: str | Path | None = None) -> dict:
    """Return a read-only, path-free diagnostic report for selected local hosts.

    ``ready`` means Python is supported and at least one selected installation
    has a valid skill entrypoint and local references. Dependency versions are
    inspected via package metadata; this is not an image decode or SDK test.
    """
    if host not in {*HOSTS, "both", "auto"}:
        raise ValueError("host must be claude, codex, both or auto")
    home = Path(home if home is not None else Path.home()).expanduser().resolve()
    selected = list(HOSTS) if host in {"both", "auto"} else [host]
    if host == "auto":
        present = [name for name in selected if os.path.lexists(home / HOSTS[name] / "skills" / "naturale")]
        selected = present or selected
    supported_python = tuple(sys.version_info[:2]) >= (3, 11)
    pillow_version = _package_version("Pillow")
    pillow_match = re.match(r"(\d+)\.", pillow_version or "")
    pillow_compatible = bool(pillow_match and 11 <= int(pillow_match.group(1)) < 13)
    c2pa_version = _package_version("c2pa-python")
    exiftool = _exiftool_report()
    hosts = []
    for name in selected:
        try:
            hosts.append(_host_report(name, home))
        except (OSError, UnicodeError, ValueError):
            hosts.append({"host": name, "version": None, "text_ready": False,
                          "missing": ["installation_unreadable"], "warnings": [],
                          "receipt": "unreadable"})
    return {
        "schema_version": "1.0",
        "python": {"version": ".".join(map(str, sys.version_info[:3])), "supported": supported_python},
        "hosts": hosts,
        "dependencies": {
            "pillow": {"available": pillow_version is not None, "version": pillow_version,
                       "compatible": pillow_compatible, "checked_by": "package_metadata"},
            "exiftool": exiftool,
            "c2pa": {"available": c2pa_version is not None, "version": c2pa_version,
                     "optional": True, "checked_by": "package_metadata"},
        },
        "images_ready": supported_python and pillow_compatible and exiftool["available"],
        "ready": supported_python and any(item["text_ready"] for item in hosts),
        "network_used": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=["auto", "claude", "codex", "both"], default="both")
    args = parser.parse_args(argv)
    try:
        report = doctor(args.host)
    except (OSError, UnicodeError, ValueError):
        print(json.dumps({"schema_version": "1.0", "ready": False,
                          "error": "diagnosis_unavailable"}))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
