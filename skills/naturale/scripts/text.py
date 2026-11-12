#!/usr/bin/env python3
"""Profili di voce e controlli locali delle riscritture, senza chiamate a modelli."""
from __future__ import annotations

import argparse
from collections import Counter
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import unicodedata

SCHEMA_VERSION = "1.0"
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_STDIN_BYTES = 16 * 1024 * 1024
PROFILE_FIELDS = {
    "schema_version", "name", "register", "conciseness", "preferred_phrases",
    "avoided_phrases", "punctuation", "notes",
}
PROFILE_LIST_FIELDS = ("preferred_phrases", "avoided_phrases", "punctuation", "notes")
RESERVED_NAMES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                  *(f"lpt{i}" for i in range(1, 10))}
URL_PATTERN = re.compile(r"https?://[^\s<>\"“”«»]+", re.I)
NUMBER_PATTERN = re.compile(
    r"(?<![\w])(?:(?:[+\-−][^\S\r\n]*)?[€$£][^\S\r\n]*)?(?:[+\-−][^\S\r\n]*)?\d+(?:[.,:/-]\d+)*(?:[^\S\r\n]*(?:%|€|\$|£))?(?!\d)"
)
QUOTE_PATTERN = re.compile(r'«([^«»\n]{1,2000})»|“([^“”\n]{1,2000})”|"([^"\n]{1,2000})"')
TIME_PATTERN = re.compile(r"\b(?:alle|ore)\s+([01]?\d|2[0-3])[:.]([0-5]\d)\b", re.I)
NUMBER_WORDS = dict(zip(
    ("uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove", "dieci",
     "undici", "dodici", "tredici", "quattordici", "quindici", "sedici", "diciassette",
     "diciotto", "diciannove", "venti", "trenta", "quaranta", "cinquanta", "sessanta",
     "settanta", "ottanta", "novanta", "cento", "mille"),
    (*range(1, 21), 30, 40, 50, 60, 70, 80, 90, 100, 1000),
))
NUMBER_WORD_PATTERN = re.compile(r"\b(?:" + "|".join(NUMBER_WORDS) + r")\b", re.I)
CALENDAR_PATTERN = re.compile(
    r"\b(?:luned[ìi]|marted[ìi]|mercoled[ìi]|gioved[ìi]|venerd[ìi]|sabato|domenica|"
    r"gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\b", re.I
)
MARKER_PATTERNS = {
    "negation": re.compile(r"\b(?:non|mai|nessun[oa]?|senza|né|niente|nulla|neanche|nemmeno|neppure)\b", re.I),
    "uncertainty": re.compile(
        r"\b(?:forse|potrebbe|potrebbero|potremmo|potrei|possibile|probabile|"
        r"ipotizziamo|indicativamente|circa|previsto|prevista|dovrebbe|dovremmo|probabilmente|eventualmente)\b", re.I
    ),
    "condition": re.compile(r"\b(?:se|salvo|purché|qualora|a condizione che|a patto che|solo dopo)\b", re.I),
    "deadline": re.compile(r"\b(?:entro|prima di|non oltre|fino a|a partire da)\b", re.I),
}


class TextError(ValueError):
    """Input o operazione locale non validi."""


def _read_text(path: str | Path) -> str:
    """Legge soltanto un file regolare UTF-8, senza seguire symlink finali/FIFO."""
    path = Path(path).expanduser().absolute()
    try:
        if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
            raise TextError(f"File non regolare o collegamento simbolico: {path}")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise TextError(f"File non regolare: {path}")
            content = stream.read(MAX_INPUT_BYTES + 1)
        if len(content) > MAX_INPUT_BYTES:
            raise TextError("Input oltre il limite di 2 MiB.")
        return content.decode("utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise TextError(f"File UTF-8 non leggibile: {path}: {error}") from error


def _read_json(path: str | Path):
    try:
        return json.loads(_read_text(path))
    except json.JSONDecodeError as error:
        raise TextError(f"JSON non valido alla riga {error.lineno}.") from error


def _profile_name(name: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise TextError("Il nome del profilo deve usare minuscole, numeri e trattini, senza percorsi.")
    if len(name) > 64 or name in RESERVED_NAMES:
        raise TextError("Nome del profilo troppo lungo o riservato dal sistema operativo.")
    return name


def _short_text(value, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise TextError(f"{field}: serve un testo non vuoto di massimo {limit} caratteri.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise TextError(f"{field}: testo Unicode non codificabile in UTF-8.") from error
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise TextError(f"{field}: caratteri di controllo non ammessi.")
    return value.strip()


def validate_profile(data, name: str | None = None) -> dict:
    """Whitelist di caratteristiche stilistiche; non accetta campioni o biografie."""
    if not isinstance(data, dict) or set(data) - PROFILE_FIELDS:
        raise TextError("Profilo non valido: usare soltanto i campi stilistici documentati.")
    chosen = _profile_name(name if name is not None else data.get("name"))
    if "name" in data and data["name"] != chosen:
        raise TextError("Il nome nel JSON deve coincidere con il nome richiesto.")
    if data.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise TextError("Versione dello schema profilo non supportata.")
    result = {
        "schema_version": SCHEMA_VERSION, "name": chosen,
        "register": _short_text(data.get("register"), "register", 160),
        "conciseness": _short_text(data.get("conciseness"), "conciseness", 160),
    }
    for field in PROFILE_LIST_FIELDS:
        values = data.get(field, [])
        if not isinstance(values, list) or len(values) > 20:
            raise TextError(f"{field}: usare una lista di massimo 20 elementi.")
        result[field] = [_short_text(value, field, 240) for value in values]
    return result


def _profile_directory(directory: str | Path | None = None, create: bool = False) -> Path:
    target = Path(directory).expanduser().absolute() if directory is not None else Path.home() / ".naturale" / "profiles"
    current = Path(target.anchor)
    for part in target.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise TextError(f"Collegamento simbolico nella directory dei profili: {current}")
        if current.exists():
            if not current.is_dir():
                raise TextError(f"La directory dei profili contiene un file: {current}")
        elif create:
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                if current.is_symlink() or not current.is_dir():
                    raise TextError(f"Directory profili non sicura: {current}")
    return target


def create_profile(name: str, data, directory: str | Path | None = None) -> dict:
    """Salvataggio esplicito, privato e senza sovrascritture; restituisce il profilo."""
    name = _profile_name(name)
    profile = validate_profile(data, name)
    # Serializza prima di creare directory o file: un errore di codifica non
    # deve lasciare un profilo parziale che impedisca un tentativo successivo.
    content = (json.dumps(profile, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = _profile_directory(directory, create=True) / f"{name}.json"
    fd = None
    created = False
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        created = True
        with os.fdopen(fd, "wb") as stream:
            fd = None
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise TextError(f"Il profilo esiste già e non viene sovrascritto: {name}") from error
    except (OSError, UnicodeError) as error:
        if created:
            target.unlink(missing_ok=True)
        raise TextError(f"Profilo non salvato: {error}") from error
    finally:
        if fd is not None:
            os.close(fd)
    return profile


def show_profile(name: str, directory: str | Path | None = None) -> dict:
    name = _profile_name(name)
    path = _profile_directory(directory) / f"{name}.json"
    return validate_profile(_read_json(path), name)


def list_profiles(directory: str | Path | None = None) -> list[dict]:
    target = _profile_directory(directory)
    if not target.exists():
        return []
    result = []
    for path in sorted(target.glob("*.json")):
        profile = show_profile(path.stem, target)
        result.append({key: profile[key] for key in ("name", "register", "conciseness")})
    return result


def delete_profile(name: str, directory: str | Path | None = None) -> dict:
    name = _profile_name(name)
    target = _profile_directory(directory) / f"{name}.json"
    try:
        if target.is_symlink() or not stat.S_ISREG(target.lstat().st_mode):
            raise TextError("Il profilo non è un file regolare: cancellazione rifiutata.")
        target.unlink()
    except OSError as error:
        raise TextError(f"Profilo non cancellato: {error}") from error
    return {"deleted": name}


def _urls(text: str) -> list[str]:
    result = []
    for match in URL_PATTERN.finditer(text):
        url = match.group().rstrip(".,;!")
        for closing, opening in ((")", "("), ("]", "["), ("}", "{")):
            while url.endswith(closing) and url.count(closing) > url.count(opening):
                url = url[:-1]
        result.append(url)
    return result


def _numbers(text: str) -> list[str]:
    # Il contenuto degli URL è controllato separatamente, non come numeri nel testo.
    masked = URL_PATTERN.sub(" ", text)
    times = []
    def take_time(match):
        times.append(f"{int(match[1]):02d}:{match[2]}")
        return " " * len(match.group())
    masked = TIME_PATTERN.sub(take_time, masked)
    numbers = []
    for match in NUMBER_PATTERN.finditer(masked):
        value = re.sub(r"\s+", "", match.group()).replace("−", "-")
        if "€" in value:
            amount = value.replace("€", "")
            # La posizione del simbolo è sempre una variazione di forma,
            # anche quando i separatori numerici restano letterali.
            value = f"€{amount}"
            integer, separator, fraction = amount.partition(",")
            # Solo la notazione italiana non ambigua: gruppi di migliaia,
            # virgola decimale. Non reinterpretare identificativi generici.
            if re.fullmatch(r"[+-]?(?:\d+|\d{1,3}(?:\.\d{3})+)", integer) and (
                    not separator or fraction.isdigit()):
                integer = integer.replace(".", "")
                sign = "-" if integer.startswith("-") else ""
                integer = integer.lstrip("+-").lstrip("0") or "0"
                fraction = fraction.rstrip("0").ljust(2, "0")
                value = f"€{sign}{integer},{fraction}"
        numbers.append(value)
    numbers.extend(str(NUMBER_WORDS[m.group().casefold()]) for m in NUMBER_WORD_PATTERN.finditer(masked))
    return numbers + times


def _calendar(text: str) -> list[str]:
    text = URL_PATTERN.sub(" ", unicodedata.normalize("NFC", text))
    return [m.group().casefold().replace("ì", "i") for m in CALENDAR_PATTERN.finditer(text)]


def _quotes(text: str) -> list[str]:
    return [next(group for group in match.groups() if group is not None) for match in QUOTE_PATTERN.finditer(text)]


def _value_detail(kind: str, value: str) -> dict:
    if kind == "quoted_text" or len(value) > 256:
        return {"preview": value[:80], "characters": len(value),
                "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest()}
    return {"value": value}


def validate_constraints(data) -> dict:
    if data is None:
        return {"preserve_exact": [], "forbid": []}
    if not isinstance(data, dict) or set(data) - {"preserve_exact", "forbid"}:
        raise TextError("Vincoli non validi: usare preserve_exact e/o forbid.")
    result = {}
    for field in ("preserve_exact", "forbid"):
        values = data.get(field, [])
        if not isinstance(values, list) or len(values) > 100:
            raise TextError(f"{field}: usare una lista di massimo 100 testi.")
        result[field] = [_short_text(value, field, 2000) for value in values]
        if len(set(result[field])) != len(result[field]):
            raise TextError(f"{field}: vincoli duplicati.")
    if set(result["preserve_exact"]) & set(result["forbid"]):
        raise TextError("Una stessa espressione non può essere richiesta e vietata.")
    return result


def _unified_diff(source: str, revision: str) -> str:
    lines = difflib.unified_diff(source.splitlines(keepends=True), revision.splitlines(keepends=True),
                                 fromfile="source", tofile="revision")
    return "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in lines)


def audit_text(source: str, revision: str, constraints=None, include_diff: bool = False,
               operation: str = "rewrite") -> dict:
    """Confronto meccanico + indicatori da rileggere, senza giudizi di verità."""
    if operation not in {"rewrite", "summarize"}:
        raise TextError("Operazione audit non supportata.")
    if not isinstance(source, str) or not isinstance(revision, str):
        raise TextError("Fonte e revisione devono essere testi.")
    if not source.strip():
        raise TextError("La fonte non può essere vuota.")
    if max(len(source.encode("utf-8")), len(revision.encode("utf-8"))) > MAX_INPUT_BYTES:
        raise TextError("Testo oltre il limite di 2 MiB.")
    constraints = validate_constraints(constraints)
    for value in constraints["preserve_exact"]:
        if value not in source:
            raise TextError("Un vincolo preserve_exact non compare nella fonte.")
    findings = []
    for kind, extractor in (("number", _numbers), ("calendar", _calendar), ("url", _urls), ("quoted_text", _quotes)):
        before, after = Counter(extractor(source)), Counter(extractor(revision))
        for value in sorted(before.keys() | after.keys()):
            if before[value] == after[value]:
                continue
            change = "added" if after[value] > before[value] else "missing"
            if operation == "summarize" and change == "missing":
                continue
            findings.append({"kind": kind, "change": change, **_value_detail(kind, value),
                             "source_count": before[value], "revision_count": after[value]})
    if not revision.strip():
        findings.append({"kind": "empty_revision", "change": "missing"})
    for value in constraints["preserve_exact"]:
        if value not in revision:
            findings.append({"kind": "required_text", "change": "missing", "value": value})
    for value in constraints["forbid"]:
        if value in revision:
            findings.append({"kind": "forbidden_text", "change": "added", "value": value})
    review_flags = []
    marker_source = re.sub(r"\s+", " ", unicodedata.normalize("NFC", source))
    marker_revision = re.sub(r"\s+", " ", unicodedata.normalize("NFC", revision))
    for category, pattern in MARKER_PATTERNS.items():
        before = Counter(match.group().casefold() for match in pattern.finditer(marker_source))
        after = Counter(match.group().casefold() for match in pattern.finditer(marker_revision))
        if before != after:
            review_flags.append({"category": category, "source_markers": dict(before), "revision_markers": dict(after),
                                 "message": "Indicatori linguistici cambiati: rileggere nel contesto; non è una prova di errore."})
    result = {
        "schema_version": SCHEMA_VERSION, "operation": operation,
        "unchanged": source == revision,
        "deterministic_status": "issues_found" if findings else "passed",
        "review_status": "required" if findings or review_flags else "not_required",
        "semantic_equivalence": "not_verified", "human_review_required": True,
        "findings": findings, "review_flags": review_flags,
        "counts": {"source_characters": len(source), "revision_characters": len(revision)},
        "limitations": [
            "I controlli meccanici possono segnalare variazioni lecite di forma o ripetizione.",
            "Nomi, unità, responsabilità, causalità, fatti aggiunti e significato richiedono una verifica separata.",
            "L'assenza di segnalazioni non dimostra equivalenza semantica o verità del testo.",
        ],
    }
    if include_diff:
        result["diff"] = _unified_diff(source, revision)
    return result


def audit_files(source: str | Path, revision: str | Path, constraints: str | Path | None = None,
                include_diff: bool = False, operation: str = "rewrite") -> dict:
    return audit_text(_read_text(source), _read_text(revision),
                      _read_json(constraints) if constraints is not None else None, include_diff, operation)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    profiles = commands.add_parser("profiles", help="Profili stilistici espliciti, salvati localmente")
    actions = profiles.add_subparsers(dest="profile_action", required=True)
    for action in ("create", "show", "list", "delete"):
        command = actions.add_parser(action)
        if action != "list":
            command.add_argument("name")
        command.add_argument("--directory", help="Directory profili; default ~/.naturale/profiles")
        if action == "create":
            command.add_argument("--from-json", required=True)
    audit = commands.add_parser("audit", help="Controlli locali: non certifica il significato")
    inputs = audit.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--source")
    inputs.add_argument("--stdin-json", action="store_true", help="JSON UTF-8 da stdin, senza file temporanei")
    audit.add_argument("--revision")
    audit.add_argument("--constraints")
    audit.add_argument("--operation", choices=["rewrite", "summarize"], default="rewrite")
    audit.add_argument("--diff", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "audit":
        if args.stdin_json and (args.revision is not None or args.constraints is not None):
            parser.error("--stdin-json non accetta --revision o --constraints su file")
        if not args.stdin_json and args.revision is None:
            parser.error("--source richiede --revision")
    try:
        if args.command == "audit":
            if args.stdin_json:
                stream = getattr(sys.stdin, "buffer", sys.stdin)
                raw = stream.read(MAX_STDIN_BYTES + 1)
                if isinstance(raw, str):
                    raw = raw.encode("utf-8")
                if len(raw) > MAX_STDIN_BYTES:
                    raise TextError("JSON stdin oltre il limite di 16 MiB.")
                try:
                    data = json.loads(raw.decode("utf-8-sig"))
                except (ValueError, UnicodeError) as error:
                    raise TextError("JSON UTF-8 da stdin non valido.") from error
                if not isinstance(data, dict) or not {"source", "revision"} <= data.keys() or data.keys() - {"source", "revision", "constraints"}:
                    raise TextError("JSON stdin richiede source e revision, con constraints facoltativo.")
                result = audit_text(data["source"], data["revision"], data.get("constraints"), args.diff, args.operation)
            else:
                result = audit_files(args.source, args.revision, args.constraints, args.diff, args.operation)
            status = 1 if result["findings"] else 3 if result["review_flags"] else 0
        else:
            directory = args.directory
            if args.profile_action == "create":
                result = create_profile(args.name, _read_json(args.from_json), directory)
            elif args.profile_action == "show":
                result = show_profile(args.name, directory)
            elif args.profile_action == "list":
                result = {"profiles": list_profiles(directory)}
            else:
                result = delete_profile(args.name, directory)
            status = 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return status
    except (TextError, OSError, UnicodeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
